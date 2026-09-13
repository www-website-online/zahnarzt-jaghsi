"""Send contact requests over authenticated, encrypted SMTP; never log bodies."""
import logging
import os
import re
import smtplib
import ssl
from email.message import EmailMessage

logger = logging.getLogger(__name__)


def configured():
    return all(os.getenv(key) for key in ("SMTP_HOST", "SMTP_FROM", "CONTACT_TO"))


def valid_email(value):
    return len(value) <= 254 and bool(re.fullmatch(r"[^\s@<>\r\n]+@[^\s@<>\r\n]+\.[^\s@<>\r\n]+", value))


def deliver(name, email, message):
    if not configured():
        return False
    sender = os.environ["SMTP_FROM"]
    recipient = os.environ["CONTACT_TO"]
    if not valid_email(sender) or not valid_email(recipient):
        logger.error("Contact mail configuration has an invalid address")
        return False
    mail = EmailMessage()
    mail["From"] = sender
    mail["To"] = recipient
    mail["Reply-To"] = email
    mail["Subject"] = "Kontaktanfrage / رسالة تواصل — Zahnarztpraxis"
    mail.set_content(f"Name: {name}\nE-Mail: {email}\n\n{message}")
    try:
        mode = os.getenv("SMTP_SECURITY", "starttls")
        if mode not in {"starttls", "ssl"}:
            raise ValueError("SMTP_SECURITY must be starttls or ssl")
        context = ssl.create_default_context()
        port = int(os.getenv("SMTP_PORT", "465" if mode == "ssl" else "587"))
        factory = smtplib.SMTP_SSL if mode == "ssl" else smtplib.SMTP
        kwargs = {"context": context} if mode == "ssl" else {}
        with factory(os.environ["SMTP_HOST"], port, timeout=10, **kwargs) as client:
            if mode == "starttls":
                client.ehlo()
                client.starttls(context=context)
                client.ehlo()
            if os.getenv("SMTP_USER"):
                client.login(os.environ["SMTP_USER"], os.environ.get("SMTP_PASSWORD", ""))
            refused = client.send_message(mail)
            return not refused
    except (OSError, smtplib.SMTPException, ValueError) as exc:
        # SMTP errors can contain message content or addresses: log type only.
        logger.error("Contact delivery failed (%s)", type(exc).__name__)
        return False
