"""Mailgun transport.

| Variable | Default |
| --- | --- |
| ``MAILGUN_API_KEY`` | required |
| ``MAILGUN_DOMAIN`` | required |
| ``MAILGUN_API_URL`` | ``https://api.mailgun.net`` (EU: ``https://api.eu.mailgun.net``) |
| ``MAIL_FROM`` | required |
"""

import os

import httpx

from .. import settings
from .message import MailMessage, env


def send(message: MailMessage) -> None:
    api = (os.environ.get("MAILGUN_API_URL") or "https://api.mailgun.net").rstrip("/")
    response = httpx.post(
        f"{api}/v3/{env('MAILGUN_DOMAIN')}/messages",
        auth=("api", env("MAILGUN_API_KEY")),
        data={
            "from": settings.MAIL_FROM or env("MAIL_FROM"),
            "to": message.to,
            "subject": message.subject,
            "text": message.text,
            "html": message.html,
        },
        timeout=15,
    )
    response.raise_for_status()
