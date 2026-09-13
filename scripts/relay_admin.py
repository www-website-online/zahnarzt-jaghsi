#!/usr/bin/env python3
"""Relay preflight, consistent backup and operator recovery. Never prints secrets."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import secrets
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app.mail_relay import Relay, Settings
from backend.app import relay_group


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', type=Path)
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('preflight')
    sub.add_parser('status')
    init=sub.add_parser('create-config');init.add_argument('path',type=Path)
    backup=sub.add_parser('backup');backup.add_argument('destination',type=Path)
    verify=sub.add_parser('verify-backup');verify.add_argument('path',type=Path)
    recover=sub.add_parser('resolve');recover.add_argument('id')
    recover.add_argument('--action',choices=('retry','accepted','cancel'),required=True)
    recover.add_argument('--confirm-delivery-checked',action='store_true',required=True)
    close=sub.add_parser('close');close.add_argument('conversation')
    args=parser.parse_args()
    if args.command=='create-config':
        # New file only; does not change service configuration or initialize data.
        content=(
            'MAIL_RELAY_ENABLED=0\nMAIL_RELAY_RECEIVE_ENABLED=1\n'
            'MAIL_RELAY_DATA_DIR=/var/lib/zahnarzt-relay\n'
            'MAIL_RELAY_CLINICIAN=tamerfaowr@gmail.com\n'
            'MAIL_RELAY_REPLY_DOMAIN=reply.zahnarzt-jaghsi.de\n'
            f'MAIL_RELAY_WEBHOOK_SECRET={secrets.token_hex(32)}\n'
            f'MAIL_RELAY_TOKEN_SECRET={secrets.token_hex(32)}\n'
            'SMTP_HOST=smtp-relay.gmail.com\nSMTP_PORT=587\nSMTP_SECURITY=starttls\n'
            'SMTP_FROM=info@zahnarzt-jaghsi.de\n')
        fd=os.open(args.path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'w') as target:target.write(content)
        print('Configuration created (0600); secrets not displayed.')
        return
    if args.command=='verify-backup':
        with sqlite3.connect(args.path.resolve().as_uri()+'?mode=ro',uri=True) as db:
            if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise RuntimeError('Backup corrupt')
            print(json.dumps({'integrity':'ok','conversations':db.execute('SELECT count(*) FROM conversations').fetchone()[0],
                              'outbox':db.execute('SELECT count(*) FROM outbox').fetchone()[0]}))
        return
    if args.env_file:
        if args.env_file.stat().st_mode & 0o077:raise ValueError('Environment file must be private')
        for line in args.env_file.read_text().splitlines():
            if not line or line.startswith('#'):continue
            key,sep,value=line.partition('=')
            if not sep or not key.replace('_','').isalnum():raise ValueError('Invalid environment file')
            os.environ[key]=value
    settings=Settings.from_environment()
    if args.command=='preflight':
        # Read-only: no production database is created by this command.
        members = relay_group.load_members(settings.group_members_file, settings.group_address, settings.token_secret) if settings.group_address else ()
        print(json.dumps({'config':'valid','clinician':settings.group_address or settings.clinician,'sender':settings.sender,
                          'group_mode':bool(settings.group_address),'group_member_count':len(members),
                          'reply_domain':settings.reply_domain,'db_exists':(settings.directory/'relay.sqlite3').exists()}))
        return
    if not (settings.directory/'relay.sqlite3').is_file():raise ValueError('Database is not initialized')
    relay=Relay(settings)
    if args.command=='status':print(json.dumps(relay.status()))
    elif args.command=='backup':
        args.destination.mkdir(parents=True,exist_ok=True,mode=0o700)
        if args.destination.stat().st_mode & 0o077:raise ValueError('Backup directory must be private')
        path=args.destination/('relay-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.sqlite3')
        relay.backup(path);print(str(path))
    elif args.command=='resolve':
        status={'retry':'queued','accepted':'accepted','cancel':'cancelled'}[args.action]
        with relay.db() as db:
            row=db.execute('SELECT status FROM outbox WHERE id=?',(args.id,)).fetchone()
            if not row or row[0] not in {'failed','uncertain'}:raise ValueError('Not an item requiring review')
            db.execute('UPDATE outbox SET status=?,available=?,last_error=?,attempts=0 WHERE id=?',
                       (status,relay.clock(),'operator_'+args.action,args.id))
            db.execute('INSERT INTO audit(created,action,item) VALUES(?,?,?)',(relay.clock(),args.action,args.id))
        print('Delivery resolution recorded.')
    elif args.command=='close':
        with relay.db() as db:
            if not db.execute('SELECT 1 FROM conversations WHERE id=?',(args.conversation,)).fetchone():raise ValueError('Unknown conversation')
            db.execute('UPDATE conversations SET closed=1 WHERE id=?',(args.conversation,))
            db.execute('INSERT INTO audit(created,action,item) VALUES(?,?,?)',(relay.clock(),'close',args.conversation))
        print('Conversation closed to new replies; history preserved.')


if __name__=='__main__':main()
