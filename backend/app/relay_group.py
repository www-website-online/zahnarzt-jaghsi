"""Read a short-lived, signed snapshot of Google Group membership. No I/O on import."""
import hashlib
import hmac
import json
import math
from pathlib import Path
import time

from .contact import valid_email

MAX_AGE = 300
MAX_BYTES = 256 * 1024
MAX_MEMBERS = 500


class MembershipUnavailable(ValueError):
    def __init__(self):
        super().__init__('group_members_unavailable')


def signature(payload, secret):
    key = hmac.new(secret.encode(), b'clinic-group-members-v1', hashlib.sha256).digest()
    body = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()
    return hmac.new(key, body, hashlib.sha256).hexdigest()


def snapshot(group, members, secret, now=None):
    payload = {'version': 1, 'group': group.casefold(), 'checked_at': time.time() if now is None else now,
               'members': sorted(set(m.casefold() for m in members))}
    return {'payload': payload, 'signature': signature(payload, secret)}


def load_members(path, group, secret, now=None):
    """Never use stale, partially written, mismatched or unsigned membership."""
    try:
        with Path(path).open('rb') as source:
            raw = source.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError()
        value = json.loads(raw)
        payload = value['payload']
        if not hmac.compare_digest(value['signature'], signature(payload, secret)):
            raise ValueError()
        current = time.time() if now is None else now
        checked = payload['checked_at']
        if (payload['version'] != 1 or payload['group'] != group.casefold()
                or type(checked) not in (int, float) or not math.isfinite(checked)
                or not -30 <= current - checked <= MAX_AGE):
            raise ValueError()
        members = payload['members']
        if not isinstance(members, list) or not 1 <= len(members) <= MAX_MEMBERS:
            raise ValueError()
        if any(not isinstance(m, str) or not m.isascii() or not valid_email(m)
               or m != m.casefold() or m == group.casefold() for m in members):
            raise ValueError()
        return frozenset(members)
    except (OSError, ValueError, KeyError, TypeError, AttributeError, RecursionError):
        raise MembershipUnavailable() from None
