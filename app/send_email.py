# app/send_email.py
import smtplib
from email.message import EmailMessage

TO_EMAIL = "info@zahnarzt-jaghsi.de"  # البريد الذي سيصل إليه كل شيء

def send_contact_email(name: str, email: str, message: str) -> None:
    """
    يرسل رسالة من نموذج التواصل إلى عيادة الأسنان.
    """
    body = f"""Neue Kontaktanfrage von der Webseite

Name: {name}
E-Mail: {email}

Nachricht:
{message}
"""

    msg = EmailMessage()
    msg["Subject"] = f"Neue Nachricht von {name}"
    msg["From"] = f"Kontaktformular <info@zahnarzt-jaghsi.de>"
    msg["To"] = TO_EMAIL
    msg["Reply-To"] = email   # مهم: حتى زر Reply يرد إلى الزائر
    msg.set_content(body)

    # نستخدم Postfix المحلي على المنفذ 25
    with smtplib.SMTP("localhost", 25) as server:
        server.send_message(msg)
