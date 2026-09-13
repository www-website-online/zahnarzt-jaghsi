"""Browser request protection and bounded local abuse controls."""
import hashlib
import hmac
import os
import secrets
import threading
import time
from collections import OrderedDict, deque
from urllib.parse import urlsplit

from fastapi import Form, HTTPException, Request
from starlette.responses import PlainTextResponse

SITE_URL = os.getenv("SITE_URL", "https://zahnarzt-jaghsi.de").rstrip("/")
COOKIE = "clinic_csrf"
_key = hashlib.sha256(os.getenv("CSRF_SECRET", os.getenv("ADMIN_UPLOAD_PASSWORD", "")).encode() or secrets.token_bytes(32)).digest()
TOKEN_TTL = 7200
MAX_REQUEST_BYTES = 32 * 1024 * 1024


def make_token():
    value = f"{int(time.time())}.{secrets.token_hex(24)}"
    return value + "." + hmac.new(_key, value.encode(), hashlib.sha256).hexdigest()


def valid_token(token):
    try:
        stamp, random, signature = token.split(".")
        age = time.time() - int(stamp)
        expected = hmac.new(_key, f"{stamp}.{random}".encode(), hashlib.sha256).hexdigest()
        return 0 <= age <= TOKEN_TTL and secrets.compare_digest(signature, expected)
    except (ValueError, TypeError, AttributeError):
        return False


def verify_csrf(request: Request, csrf_token: str = Form("")):
    cookie = request.cookies.get(COOKIE, "")
    if not valid_token(cookie) or not secrets.compare_digest(cookie.encode(), csrf_token.encode()):
        raise HTTPException(403, "Please reload the form and try again.")
    origin = request.headers.get("origin")
    referer = request.headers.get("referer")
    if origin or referer:
        source = urlsplit(origin or referer)
        source_origin = f"{source.scheme}://{source.netloc}"
        # SITE_URL is trusted configuration; never derive trust from Host.
        if source_origin != SITE_URL:
            raise HTTPException(403, "Cross-origin submission rejected.")


class RateLimiter:
    def __init__(self):
        self.rows = OrderedDict()
        self.lock = threading.Lock()

    def allow(self, key, limit, period, record=True):
        now = time.monotonic()
        with self.lock:
            queue = self.rows.setdefault(key, deque())
            self.rows.move_to_end(key)
            while queue and queue[0] <= now - period:
                queue.popleft()
            if len(queue) >= limit:
                return False
            if record:
                queue.append(now)
            while len(self.rows) > 4096:
                self.rows.popitem(last=False)
            return True


limiter = RateLimiter()


class BodyTooLarge(Exception):
    pass


class RequestSizeLimit:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers", []))
        try:
            length = int(headers.get(b"content-length", b"0"))
        except ValueError:
            return await PlainTextResponse("Invalid request length", 400)(scope, receive, send)
        if length > MAX_REQUEST_BYTES:
            return await PlainTextResponse("Request too large", 413)(scope, receive, send)
        consumed = 0

        async def bounded_receive():
            nonlocal consumed
            message = await receive()
            consumed += len(message.get("body", b""))
            if consumed > MAX_REQUEST_BYTES:
                raise HTTPException(413, "Request too large")
            return message

        await self.app(scope, bounded_receive, send)
