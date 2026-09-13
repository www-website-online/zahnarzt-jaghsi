"""Rebuild relay emails instead of forwarding private headers or quoted mail."""
from email import policy
from email.headerregistry import Address
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import formatdate
from html.parser import HTMLParser
import re
import smtplib
import ssl

from .mail_presentation import presentation

MAX_RAW = 512 * 1024
MAX_TEXT = 20000
MARKER = '--- Praxis-Korrespondenz / مراسلات العيادة ---'
EMAIL_RE = re.compile(r'[\w.!#$%&\'*+/=?^`{|}~-]+@[\w.-]+\.[A-Za-z]{2,}', re.UNICODE)


class InvalidMail(ValueError):
    """Only fixed reason codes, never mail content, may be logged."""


class TextHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.stack = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        excluded = tag in {'script', 'style', 'head', 'blockquote'} or any(
            word in attrs.get('class', '') for word in ('gmail_quote', 'gmail_attr', 'yahoo_quoted', 'protonmail_quote', 'clinic-footer'))
        if tag not in {'br', 'img', 'hr', 'meta', 'link', 'input'}:
            self.stack.append((tag, excluded or any(x[1] for x in self.stack)))
        if tag in {'br', 'p', 'div', 'li', 'tr', 'hr'}:
            self.parts.append('\n')

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break
        if tag in {'p', 'div', 'li', 'tr'}:
            self.parts.append('\n')

    def handle_data(self, data):
        if not any(x[1] for x in self.stack):
            self.parts.append(data)



# Ignore direction controls only when recognizing an automatically generated header.
# Keep them in ordinary user text, where they can affect intended mixed-language layout.
QUOTE_DIRECTION_CONTROLS = str.maketrans('', '', '\u061c\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069')
QUOTE_HEADER = re.compile(r'^(On .{3,}wrote:|Am .{3,}schrieb.{0,}:|في .{3,}(كتب|كتبت|تمت كتابة).{0,}:)')


def quoted_header_at(source_lines, index):
    """Recognize one Gmail attribution, including up to four consecutive wrapped lines."""
    first = source_lines[index].translate(QUOTE_DIRECTION_CONTROLS).strip()
    if QUOTE_HEADER.match(first):
        return True
    if not re.match(r'^(On |Am |في )', first):
        return False
    combined = first
    for continuation in source_lines[index + 1:index + 4]:
        continuation = continuation.translate(QUOTE_DIRECTION_CONTROLS).strip()
        # Do not consume a separate paragraph or search arbitrarily far into a reply.
        if not continuation or len(combined) + len(continuation) > 1000:
            break
        combined += ' ' + continuation
        if combined.endswith(':') and re.search(r'\d', combined) and QUOTE_HEADER.match(combined):
            return True
    return False


def sanitize_text(text, private_addresses=()):
    """Conservative quote stripping; all email addresses are masked in relays."""
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    lines = []
    source_lines = text.splitlines()
    for index, line in enumerate(source_lines):
        stripped = line.strip()
        if (MARKER in line or stripped == '--' or re.match(r'^[-_]{5,}', stripped)
                or quoted_header_at(source_lines, index)
                or re.match(r'^(From|Von|De|من)\s*:', stripped, re.I)):
            break
        if stripped.startswith('>'):
            continue
        lines.append(line)
    text = '\n'.join(lines)
    for address in private_addresses:
        text = re.sub(re.escape(address), '[E-Mail]', text, flags=re.I)
    text = EMAIL_RE.sub('[E-Mail]', text)
    text = ''.join(c for c in text if c in '\n\t' or (ord(c) >= 32 and ord(c) != 127))
    if len(text) > MAX_TEXT:
        raise InvalidMail('text_too_large')
    return text.strip()


def sender_address(raw):
    if len(raw) > MAX_RAW:
        raise InvalidMail('message_too_large')
    message = BytesParser(policy=policy.default).parsebytes(raw, headersonly=True)
    if len(message.get_all('From', [])) != 1:
        raise InvalidMail('invalid_sender')
    try:
        header = message['From']
        if header.defects or len(header.addresses) != 1:
            raise InvalidMail('invalid_sender')
        address = header.addresses[0].addr_spec
        if not address.isascii() or '@' not in address:
            raise InvalidMail('invalid_sender')
        return address
    except (AttributeError, ValueError, IndexError) as exc:
        raise InvalidMail('invalid_sender') from exc


def parse_reply(raw, expected_sender, private_addresses):
    if len(raw) > MAX_RAW:
        raise InvalidMail('message_too_large')
    message = BytesParser(policy=policy.default).parsebytes(raw)
    if sender_address(raw).casefold() != expected_sender.casefold():
        raise InvalidMail('wrong_sender')
    if message.defects:
        raise InvalidMail('malformed_message')
    if (message.get('Auto-Submitted', 'no').lower() != 'no'
            or message.get('X-Autoreply') or message.get('X-Autorespond')
            or message.get('Precedence', '').lower() in {'bulk', 'junk', 'list'}
            or message.get('X-Clinic-Relay') or message.get('List-Id')):
        raise InvalidMail('automated_message')
    parts = list(message.walk())
    if len(parts) > 30:
        raise InvalidMail('too_many_parts')
    # Reject the whole message, visibly to its sender, rather than lose attachments.
    for part in parts:
        if part.defects or part.get_content_type() in {'message/rfc822', 'multipart/report'}:
            raise InvalidMail('unsupported_message')
        if part.get_filename() or part.get_content_disposition() == 'attachment':
            raise InvalidMail('attachments_not_supported')
        if not part.is_multipart() and part.get_content_type() not in {'text/plain', 'text/html'}:
            raise InvalidMail('attachments_not_supported')
    part = message.get_body(preferencelist=('plain', 'html'))
    if part is None:
        raise InvalidMail('empty_message')
    try:
        body = part.get_content()
    except (LookupError, UnicodeError, ValueError) as exc:
        raise InvalidMail('invalid_encoding') from exc
    if not isinstance(body, str):
        raise InvalidMail('invalid_encoding')
    if part.get_content_type() == 'text/html':
        parser = TextHTML()
        parser.feed(body)
        body = ''.join(parser.parts)
    text = sanitize_text(body, private_addresses)
    if not text:
        raise InvalidMail('empty_reply')
    mid = str(message.get('Message-ID', '')).strip()
    if len(mid) > 998:
        raise InvalidMail('invalid_message_id')
    return text, mid


def compose(sender, recipient, reply_to, reference, text, outbox_id, previous_id=None,
            *, patient_name='', target_role='p'):
    mail = EmailMessage()
    mail['From'] = Address(display_name='Zahnarztpraxis Dr. Jaghsi', addr_spec=sender)
    mail['To'] = recipient
    mail['Reply-To'] = Address(display_name='Zahnarztpraxis Jaghsi', addr_spec=reply_to)
    mail['Subject'] = f'Zahnarztpraxis Dr. Jaghsi – Anfrage {reference}'
    mail['Date'] = formatdate(localtime=False, usegmt=True)
    mail['Message-ID'] = f'<relay.{outbox_id}@{sender.split("@")[1]}>'
    if previous_id:
        mail['In-Reply-To'] = previous_id
        mail['References'] = previous_id
    mail['X-Clinic-Relay'] = '1'
    mail['X-Auto-Response-Suppress'] = 'All'
    # Auto-Submitted:auto-generated would suppress a human's reply at some gateways.
    plain, html, lang = presentation(text, reference, patient_name, target_role)
    mail.set_content(plain)
    mail.add_alternative(html, subtype='html')
    mail['Content-Language'] = lang
    return mail.as_bytes(policy=policy.SMTP)


def smtp_send(settings, recipient, raw):
    """Return accepted/retry/failed/uncertain; never retry an ambiguous DATA result."""
    client = None
    data_started = False
    try:
        context = ssl.create_default_context()
        if settings.smtp_security == 'ssl':
            client = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=15, context=context)
        else:
            client = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15)
            client.ehlo()
            client.starttls(context=context)
        client.ehlo()
        if settings.smtp_user:
            client.login(settings.smtp_user, settings.smtp_password)
        code, _ = client.mail(settings.sender)
        if code != 250:
            return ('retry' if 400 <= code < 500 else 'failed'), 'smtp_mail'
        code, _ = client.rcpt(recipient)
        if code not in {250, 251}:
            return ('retry' if 400 <= code < 500 else 'failed'), 'smtp_recipient'
        data_started = True
        code, _ = client.data(raw)
        if code == 250:
            return 'accepted', ''
        return ('retry' if 400 <= code < 500 else 'failed'), 'smtp_data'
    except smtplib.SMTPResponseException as exc:
        # Explicit negative replies mean the message was not accepted.
        return ('retry' if 400 <= exc.smtp_code < 500 else 'failed'), 'smtp_rejected'
    except (OSError, smtplib.SMTPException):
        return ('uncertain' if data_started else 'retry'), 'smtp_connection'
    finally:
        if client:
            # SMTP acceptance remains success even if QUIT fails.
            client.close()
