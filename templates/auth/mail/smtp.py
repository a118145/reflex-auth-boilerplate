"""SMTP transport. Works for a company mailbox, e.g. Microsoft 365 via
``smtp.office365.com:587`` with ``SMTP_SECURITY=starttls`` (the tenant must
allow SMTP AUTH for that mailbox; otherwise use the ``graph`` transport).

| Variable | Default |
| --- | --- |
| ``SMTP_HOST`` | required |
| ``SMTP_PORT`` | 587 |
| ``SMTP_SECURITY`` | ``starttls`` (or ``ssl``, or ``none`` for a local relay) |
| ``SMTP_USERNAME`` / ``SMTP_PASSWORD`` | unset = no login |
| ``MAIL_FROM`` | required |
"""

import os
import smtplib
import ssl
from email.message import EmailMessage

from .. import settings
from .message import MailMessage, env


def send(message: MailMessage) -> None:
    host = env("SMTP_HOST")
    port = int(os.environ.get("SMTP_PORT") or 587)
    security = (os.environ.get("SMTP_SECURITY") or "starttls").lower()
    if security not in ("starttls", "ssl", "none"):
        raise RuntimeError(f"SMTP_SECURITY must be starttls, ssl or none, got {security!r}")
    sender = settings.MAIL_FROM or env("MAIL_FROM")

    mail = EmailMessage()
    mail["From"] = sender
    mail["To"] = message.to
    mail["Subject"] = message.subject
    mail.set_content(message.text)
    mail.add_alternative(message.html, subtype="html")

    context = ssl.create_default_context()
    client: smtplib.SMTP
    if security == "ssl":
        client = smtplib.SMTP_SSL(host, port, timeout=15, context=context)
    else:
        client = smtplib.SMTP(host, port, timeout=15)
    with client:
        if security == "starttls":
            client.starttls(context=context)
        username = os.environ.get("SMTP_USERNAME")
        if username:
            client.login(username, env("SMTP_PASSWORD"))
        client.send_message(mail)
