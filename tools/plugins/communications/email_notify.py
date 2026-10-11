"""Optional email notifications over SMTP (sign-in codes, alerts).

Configure in .env (the password can be encrypted with `atulya.cli secrets protect`):
    ATULYA_SMTP_HOST=smtp.gmail.com
    ATULYA_SMTP_PORT=587
    ATULYA_SMTP_USER=you@example.com
    ATULYA_SMTP_PASSWORD=<app password>
    ATULYA_NOTIFY_EMAIL=you@example.com
"""
from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage


def configured() -> bool:
    return all(os.environ.get(key, "").strip() for key in
               ("ATULYA_SMTP_HOST", "ATULYA_SMTP_USER", "ATULYA_SMTP_PASSWORD", "ATULYA_NOTIFY_EMAIL"))


def send(subject: str, body: str) -> bool:
    if not configured():
        return False
    message = EmailMessage()
    message["From"] = os.environ["ATULYA_SMTP_USER"].strip()
    message["To"] = os.environ["ATULYA_NOTIFY_EMAIL"].strip()
    message["Subject"] = subject
    message.set_content(body)
    port = int(os.environ.get("ATULYA_SMTP_PORT", "587") or 587)
    host = os.environ["ATULYA_SMTP_HOST"].strip()
    context = ssl.create_default_context()
    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port, context=context, timeout=15) as smtp:
                smtp.login(message["From"], os.environ["ATULYA_SMTP_PASSWORD"])
                smtp.send_message(message)
        else:
            with smtplib.SMTP(host, port, timeout=15) as smtp:
                smtp.starttls(context=context)
                smtp.login(message["From"], os.environ["ATULYA_SMTP_PASSWORD"])
                smtp.send_message(message)
    except (OSError, smtplib.SMTPException):
        return False
    return True
