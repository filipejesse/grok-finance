"""Send the summary by e-mail through Gmail SMTP (requires a Gmail app password)."""
from __future__ import annotations

import smtplib
from email.message import EmailMessage

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465


def send_summary(gmail_address: str, app_password: str, subject: str, body: str, to: str | None = None) -> None:
    msg = EmailMessage()
    msg["From"] = gmail_address
    msg["To"] = to or gmail_address
    msg["Subject"] = subject
    msg.set_content(body)
    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=30) as smtp:
        smtp.login(gmail_address, app_password)
        smtp.send_message(msg)
