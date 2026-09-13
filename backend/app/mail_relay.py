"""Opt-in, durable, two-party email relay. No network or data writes on import."""
import asyncio
import base64
from contextlib import contextmanager
from dataclasses import dataclass, field
import hashlib
import hmac
import json
import logging
import os
from pathlib import Path
import re
import secrets
import sqlite3
import time

from . import contact, relay_mail, relay_group

logger = logging.getLogger(__name__)
ENDPOINT = '/api/mail-relay/inbound'
MAX_WEBHOOK = 720 * 1024
MAX_QUEUE = 1000


class RelayError(Exception):
    def __init__(self, code, status=422):
        self.code, self.status = code, status
        super().__init__(code)


@dataclass(frozen=True)
class Settings:
    directory: Path
    sender: str
    clinician: str
    reply_domain: str
    webhook_secret: str = field(repr=False)
    token_secret: str = field(repr=False)
    smtp_host: str = ''
    smtp_port: int = 587
    smtp_security: str = 'starttls'
    smtp_user: str = field(default='', repr=False)
    smtp_password: str = field(default='', repr=False)
    lifetime_days: int = 180
    group_address: str = ''
    group_members_file: Path | None = None

    def validate(self):
        if not all(contact.valid_email(a) and a.isascii() for a in (self.sender, self.group_address or self.clinician)):
            raise ValueError('Relay sender and clinician must be valid ASCII mailboxes')
        if not self.group_address and self.sender.casefold() == self.clinician.casefold():
            raise ValueError('Relay clinician must differ from website address')
        if not re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]{0,249}[a-z0-9])?', self.reply_domain) or '.' not in self.reply_domain:
            raise ValueError('Invalid reply domain')
        if len(self.webhook_secret) < 64 or len(self.token_secret) < 64 or self.webhook_secret == self.token_secret:
            raise ValueError('Two distinct secrets of at least 64 characters are required')
        if not self.smtp_host or self.smtp_security not in {'starttls', 'ssl'} or not 1 <= self.smtp_port <= 65535:
            raise ValueError('Encrypted SMTP must be configured')
        if self.group_address and (not self.group_members_file or self.group_address.lower().endswith('@' + self.reply_domain)):
            raise ValueError('A group membership file and a non-relay group address are required')
        if not 1 <= self.lifetime_days <= 365:
            raise ValueError('Invalid conversation lifetime')

    @classmethod
    def from_environment(cls):
        value = cls(
            directory=Path(os.getenv('MAIL_RELAY_DATA_DIR', '/var/lib/zahnarzt-relay')),
            sender=os.getenv('SMTP_FROM', ''), clinician=os.getenv('MAIL_RELAY_CLINICIAN', ''),
            reply_domain=os.getenv('MAIL_RELAY_REPLY_DOMAIN', ''),
            webhook_secret=os.getenv('MAIL_RELAY_WEBHOOK_SECRET', ''),
            token_secret=os.getenv('MAIL_RELAY_TOKEN_SECRET', ''),
            smtp_host=os.getenv('SMTP_HOST', ''), smtp_port=int(os.getenv('SMTP_PORT', '587')),
            smtp_security=os.getenv('SMTP_SECURITY', 'starttls'), smtp_user=os.getenv('SMTP_USER', ''),
            smtp_password=os.getenv('SMTP_PASSWORD', ''),
            lifetime_days=int(os.getenv('MAIL_RELAY_LIFETIME_DAYS', '180')),
            group_address=os.getenv('MAIL_RELAY_GROUP', '').strip().casefold(),
            group_members_file=Path(os.getenv('MAIL_RELAY_GROUP_MEMBERS_FILE', '/var/lib/zahnarzt-relay-members/members.json')))
        value.validate()
        return value


def enabled():
    return os.getenv('MAIL_RELAY_ENABLED') == '1'


def receiving():
    return enabled() or os.getenv('MAIL_RELAY_RECEIVE_ENABLED') == '1'


def use_for_patient(patient):
    trial = os.getenv('MAIL_RELAY_TEST_PATIENT', '').strip().casefold()
    return enabled() or (receiving() and bool(trial) and patient.strip().casefold() == trial)


SCHEMA = '''
CREATE TABLE IF NOT EXISTS conversations (
 id TEXT PRIMARY KEY, patient TEXT NOT NULL, clinician TEXT NOT NULL,
 name TEXT NOT NULL, created REAL NOT NULL, expires REAL NOT NULL,
 closed INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS events (
 event_key TEXT PRIMARY KEY, conversation_id TEXT NOT NULL,
 sender_role TEXT NOT NULL, received REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS outbox (
 id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL, target_role TEXT NOT NULL,
 recipient TEXT NOT NULL, raw BLOB NOT NULL,
 status TEXT NOT NULL DEFAULT 'queued', attempts INTEGER NOT NULL DEFAULT 0,
 available REAL NOT NULL, lease_until REAL, last_error TEXT NOT NULL DEFAULT '',
 created REAL NOT NULL, accepted REAL
);
CREATE INDEX IF NOT EXISTS outbox_pending ON outbox(status, available);
CREATE TABLE IF NOT EXISTS nonces (nonce TEXT PRIMARY KEY, created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS audit (id INTEGER PRIMARY KEY, created REAL, action TEXT, item TEXT);
PRAGMA user_version=1;
'''


class Relay:
    def __init__(self, settings, clock=time.time, transport=relay_mail.smtp_send):
        settings.validate()
        self.settings, self.clock, self.transport = settings, clock, transport
        settings.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        if settings.directory.stat().st_mode & 0o077:
            raise ValueError('Relay directory must be private (0700)')
        self.db_path = settings.directory / 'relay.sqlite3'
        if not self.db_path.exists():
            fd = os.open(self.db_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
        if self.db_path.stat().st_mode & 0o077:
            raise ValueError('Relay database must be private (0600)')
        with self.db() as db:
            version = db.execute('PRAGMA user_version').fetchone()[0]
            if version not in {0, 1}:
                raise ValueError('Unsupported relay schema')
            db.executescript(SCHEMA)

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.db_path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            db.execute('PRAGMA foreign_keys=ON')
            db.execute('PRAGMA synchronous=FULL')
            db.execute('BEGIN IMMEDIATE')
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def group_members(self):
        if not self.settings.group_address:
            return frozenset()
        try:
            return relay_group.load_members(self.settings.group_members_file,
                self.settings.group_address, self.settings.token_secret, self.clock())
        except relay_group.MembershipUnavailable:
            raise RelayError('group_members_unavailable', 503) from None

    def reply_address(self, cid, role):
        value = f'{role}.{cid}'
        signature = hmac.new(self.settings.token_secret.encode(), value.encode(), hashlib.sha256).hexdigest()[:32]
        return f'{value}.{signature}@{self.settings.reply_domain}'

    def resolve(self, recipient):
        match = re.fullmatch(r'([dp])\.([0-9a-f]{24})\.([0-9a-f]{32})@' + re.escape(self.settings.reply_domain), recipient)
        if not match or not hmac.compare_digest(self.reply_address(match[2], match[1]), recipient):
            raise RelayError('unknown_reply_address', 404)
        return match[2], match[1]

    def _capacity(self, db):
        if db.execute("SELECT count(*) FROM outbox WHERE status IN ('queued','retry','inflight','uncertain','failed')").fetchone()[0] >= MAX_QUEUE:
            raise RelayError('queue_full', 503)

    def _enqueue(self, db, conv, target_role, text):
        self._capacity(db)
        oid = secrets.token_hex(16)
        recipient = (self.settings.group_address or conv['clinician']) if target_role == 'd' else conv['patient']
        previous = db.execute('SELECT id FROM outbox WHERE conversation_id=? AND target_role=? ORDER BY created DESC LIMIT 1',
                              (conv['id'], target_role)).fetchone()
        previous_id = f'<relay.{previous[0]}@{self.settings.sender.split("@")[1]}>' if previous else None
        raw = relay_mail.compose(self.settings.sender, recipient,
                                 self.reply_address(conv['id'], target_role), conv['id'][:8].upper(),
                                 text, oid, previous_id,
                                 patient_name=relay_mail.sanitize_text(conv['name'], (conv['patient'], conv['clinician'])),
                                 target_role=target_role)
        db.execute('INSERT INTO outbox(id,conversation_id,target_role,recipient,raw,available,created) VALUES(?,?,?,?,?,?,?)',
                   (oid, conv['id'], target_role, recipient, raw, self.clock(), self.clock()))
        return oid

    def submit(self, name, patient, text):
        if not contact.valid_email(patient) or not patient.isascii():
            raise RelayError('invalid_patient')
        members = self.group_members()
        clinic_target = self.settings.group_address or self.settings.clinician
        if (patient.casefold() in {self.settings.sender.casefold(), clinic_target.casefold()} | members
                or patient.lower().endswith('@' + self.settings.reply_domain)):
            raise RelayError('invalid_patient')
        if not name.strip() or len(name) > 120 or '\n' in name or '\r' in name:
            raise RelayError('invalid_name')
        cleaned = relay_mail.sanitize_text(text, (patient, clinic_target))
        if not cleaned:
            raise RelayError('empty_message')
        now = self.clock()
        with self.db() as db:
            # Durable limits survive app restarts and multiple workers.
            if db.execute('SELECT count(*) FROM conversations WHERE patient=? AND created>?',
                          (patient.casefold(), now - 86400)).fetchone()[0] >= 10:
                raise RelayError('rate_limited', 429)
            if db.execute('SELECT count(*) FROM conversations WHERE created>?', (now - 86400,)).fetchone()[0] >= 200:
                raise RelayError('rate_limited', 429)
            cid = secrets.token_hex(12)
            db.execute('INSERT INTO conversations(id,patient,clinician,name,created,expires) VALUES(?,?,?,?,?,?)',
                       (cid, patient.casefold(), clinic_target.casefold(), name, now,
                        now + self.settings.lifetime_days * 86400))
            conv = db.execute('SELECT * FROM conversations WHERE id=?', (cid,)).fetchone()
            self._enqueue(db, conv, 'd', cleaned)
            return cid

    def verify_webhook(self, body, timestamp, nonce, signature):
        if len(body) > MAX_WEBHOOK:
            raise RelayError('message_too_large', 413)
        if not re.fullmatch(r'[0-9]{10}', timestamp or '') or abs(self.clock() - int(timestamp)) > 300:
            raise RelayError('unauthorized', 401)
        if not re.fullmatch(r'[a-f0-9]{32}', nonce or ''):
            raise RelayError('unauthorized', 401)
        digest = hashlib.sha256(body).hexdigest()
        expected = hmac.new(self.settings.webhook_secret.encode(),
                            f'POST\n{ENDPOINT}\n{timestamp}\n{nonce}\n{digest}'.encode(), hashlib.sha256).hexdigest()
        if not re.fullmatch(r'[a-f0-9]{64}', signature or '') or not hmac.compare_digest(expected, signature):
            raise RelayError('unauthorized', 401)

    def receive(self, body, timestamp, nonce, signature):
        self.verify_webhook(body, timestamp, nonce, signature)
        try:
            payload = json.loads(body)
            recipient = payload['recipient']
            raw = base64.b64decode(payload['raw'], validate=True)
            authenticated_domain = payload['authenticated_domain']
            envelope_from = payload['envelope_from']
            if not all(isinstance(x, str) for x in (recipient, authenticated_domain, envelope_from)):
                raise ValueError()
        except (ValueError, KeyError, TypeError) as exc:
            raise RelayError('invalid_payload', 400) from exc
        cid, role = self.resolve(recipient)
        members = self.group_members()
        now = self.clock()
        with self.db() as db:
            conv = db.execute('SELECT * FROM conversations WHERE id=?', (cid,)).fetchone()
            if not conv or conv['closed'] or conv['expires'] <= now:
                raise RelayError('conversation_closed', 410)
            expected = conv['clinician'] if role == 'd' else conv['patient']
            if role == 'd' and self.settings.group_address:
                try:
                    expected = relay_mail.sender_address(raw)
                except relay_mail.InvalidMail as exc:
                    raise RelayError(str(exc)) from exc
                if expected.casefold() not in members:
                    raise RelayError('not_group_member', 403)
            if authenticated_domain.lower() != expected.split('@')[1].lower() or not envelope_from:
                raise RelayError('sender_not_authenticated', 403)
            try:
                text, mid = relay_mail.parse_reply(raw, expected, (conv['patient'], conv['clinician']))
            except relay_mail.InvalidMail as exc:
                raise RelayError(str(exc)) from exc
            # CF retries may have different Received/ARC headers; Message-ID is stable.
            fingerprint = mid or hashlib.sha256(raw).hexdigest()
            event_key = hashlib.sha256(f'{cid}|{role}|{fingerprint}'.encode()).hexdigest()
            if db.execute('SELECT 1 FROM events WHERE event_key=?', (event_key,)).fetchone():
                return 'duplicate'
            if db.execute('SELECT 1 FROM nonces WHERE nonce=?', (nonce,)).fetchone():
                raise RelayError('replayed_request', 409)
            if db.execute('SELECT count(*) FROM events WHERE conversation_id=? AND received>?', (cid, now - 3600)).fetchone()[0] >= 30:
                raise RelayError('rate_limited', 429)
            # Expired webhook nonces are implementation metadata, not messages.
            db.execute('DELETE FROM nonces WHERE created<?', (now - 600,))
            db.execute('INSERT INTO nonces VALUES(?,?)', (nonce, now))
            db.execute('INSERT INTO events VALUES(?,?,?,?)', (event_key, cid, role, now))
            self._enqueue(db, conv, 'p' if role == 'd' else 'd', text)
        return 'queued'

    def drain_one(self):
        now = self.clock()
        with self.db() as db:
            # Crash after DATA could have delivered mail: never automatically resend.
            db.execute("UPDATE outbox SET status='uncertain',last_error='expired_lease' WHERE status='inflight' AND lease_until<?", (now,))
            row = db.execute("SELECT * FROM outbox WHERE status IN ('queued','retry') AND available<=? ORDER BY created LIMIT 1", (now,)).fetchone()
            if row is None:
                return False
            row = dict(row)
            db.execute("UPDATE outbox SET status='inflight',attempts=attempts+1,lease_until=? WHERE id=?", (now + 600, row['id']))
        try:
            status, error = self.transport(self.settings, row['recipient'], row['raw'])
        except Exception:
            status, error = 'uncertain', 'transport_exception'
        if status not in {'accepted', 'retry', 'failed', 'uncertain'}:
            status, error = 'uncertain', 'invalid_transport_result'
        attempts = row['attempts'] + 1
        if status == 'retry' and attempts >= 8:
            status = 'failed'
        with self.db() as db:
            db.execute('UPDATE outbox SET status=?,last_error=?,available=?,lease_until=NULL,accepted=? WHERE id=?',
                       (status, error, self.clock() + min(3600, 30 * 2 ** attempts),
                        self.clock() if status == 'accepted' else None, row['id']))
        if status in {'failed', 'uncertain'}:
            logger.error('Relay delivery requires review: id=%s status=%s', row['id'], status)
        return True

    def status(self):
        with self.db() as db:
            counts = {row[0]: row[1] for row in db.execute('SELECT status,count(*) FROM outbox GROUP BY status')}
            review = [dict(row) for row in db.execute("SELECT id,conversation_id,status,last_error,attempts,created FROM outbox WHERE status IN ('failed','uncertain') ORDER BY created LIMIT 100")]
        return {'outbox': counts, 'review': review}

    def backup(self, target):
        target = Path(target)
        fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
        with sqlite3.connect(self.db_path) as source, sqlite3.connect(target) as dest:
            source.backup(dest)
            if dest.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise ValueError('Backup integrity check failed')

    async def run(self):
        while True:
            try:
                processed = await asyncio.to_thread(self.drain_one)
            except Exception:
                logger.error('Relay queue worker unavailable')
                processed = False
            await asyncio.sleep(0.2 if processed else 5)
