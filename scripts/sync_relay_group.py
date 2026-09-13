#!/usr/bin/env python3
"""Refresh only group membership; never reads mail or prints credentials/members."""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app.contact import valid_email
from backend.app.relay_group import MAX_MEMBERS, MembershipUnavailable, snapshot

SCOPE = 'https://www.googleapis.com/auth/admin.directory.group.member.readonly'


def fetch_members(session, group):
    """Read direct USER membership; exclude explicit inactive account states."""
    url = 'https://admin.googleapis.com/admin/directory/v1/groups/' + quote(group, safe='') + '/members'
    params = {'maxResults': 200, 'includeDerivedMembership': 'false'}
    seen, members = set(), set()
    for _ in range(5):
        response = session.get(url, params=params, timeout=8, allow_redirects=False)
        if response.status_code != 200:
            raise MembershipUnavailable()
        data = response.json()
        rows = data.get('members', [])
        if not isinstance(rows, list):
            raise MembershipUnavailable()
        for member in rows:
            if member.get('type') != 'USER':
                raise MembershipUnavailable()
            email = member.get('email', '').casefold()
            if (member.get('role') not in {'MEMBER', 'MANAGER', 'OWNER'}
                    or not email.isascii() or not valid_email(email) or email == group.casefold()):
                raise MembershipUnavailable()
            if 'status' not in member:
                # members.list can omit external account status. members.get
                # returns it; verify the same member before authorizing a reply.
                detail = session.get(url + '/' + quote(email, safe=''),
                                     timeout=8, allow_redirects=False)
                if detail.status_code != 200:
                    raise MembershipUnavailable()
                member = detail.json()
                if (member.get('email', '').casefold() != email
                        or member.get('type') != 'USER'
                        or member.get('role') not in {'MEMBER', 'MANAGER', 'OWNER'}
                        or 'status' not in member):
                    raise MembershipUnavailable()
            if member['status'] != 'ACTIVE':
                continue
            members.add(email)
            if len(members) > MAX_MEMBERS:
                raise MembershipUnavailable()
        token = data.get('nextPageToken')
        if not token:
            if not members:
                raise MembershipUnavailable()
            return members
        if not isinstance(token, str) or token in seen:
            raise MembershipUnavailable()
        seen.add(token)
        params['pageToken'] = token
    raise MembershipUnavailable()


def write_snapshot(path, value):
    """Atomic replacement; root-owned directory grants application read access only."""
    path = Path(path)
    if not path.parent.is_dir():
        raise ValueError('Membership directory must be provisioned first')
    fd, temporary = tempfile.mkstemp(prefix='.members-', dir=path.parent)
    try:
        # The timer runs User=root, Group=www-data in a root-owned 0750 directory.
        os.fchmod(fd, 0o640)
        with os.fdopen(fd, 'w') as target:
            json.dump(value, target, sort_keys=True)
            target.flush()
            os.fsync(target.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)  # Only this invocation's unfinished temporary file.


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Read Google only; do not write a snapshot')
    args = parser.parse_args()
    try:
        # Isolated sync environment only. The website has no Google dependencies
        # and never receives the service-account private key.
        from google.oauth2 import service_account
        from google.auth.transport.requests import AuthorizedSession
        group = os.environ['MAIL_RELAY_GROUP'].casefold()
        admin = os.environ['MAIL_RELAY_GOOGLE_ADMIN']
        keyfile = Path(os.environ['MAIL_RELAY_GOOGLE_CREDENTIALS'])
        secret = os.environ['MAIL_RELAY_TOKEN_SECRET']
        if not valid_email(group) or not valid_email(admin) or len(secret) < 64:
            raise ValueError()
        if keyfile.stat().st_mode & 0o077:
            raise ValueError('Google credentials must be private')
        credentials = service_account.Credentials.from_service_account_file(
            keyfile, scopes=[SCOPE], subject=admin)
        with AuthorizedSession(credentials) as session:
            members = fetch_members(session, group)
        if not args.check:
            write_snapshot(os.environ['MAIL_RELAY_GROUP_MEMBERS_FILE'], snapshot(group, members, secret))
        print(json.dumps({'status': 'ok', 'member_count': len(members), 'written': not args.check}))
    except Exception:
        # Provider exceptions can contain sensitive URLs/credentials. Log fixed codes only.
        print('Group membership refresh failed; previous snapshot will expire.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
