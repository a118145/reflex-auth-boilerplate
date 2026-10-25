"""The sign-in e-mail and the transport dispatcher."""

import dataclasses
import html
import os

from .. import settings


@dataclasses.dataclass(frozen=True)
class MailMessage:
    to: str
    subject: str
    text: str
    html: str


def env(name: str) -> str:
    """A required transport variable. Raised at send time, so an app without
    mail configured still starts — the admin can sign in and fix it."""
    value = (os.environ.get(name) or "").strip()
    if not value:
        raise RuntimeError(f"{name} is required for MAIL_TRANSPORT={settings.MAIL_TRANSPORT}")
    return value


def build_message(to: str, link: str) -> MailMessage:
    minutes = int(settings.LINK_EXPIRATION.total_seconds() // 60)
    title = settings.APP_TITLE
    text = (
        f"Sign in to {title}:\n\n{link}\n\n"
        f"The link works once and expires in {minutes} minutes.\n"
        "If you did not ask for it, ignore this e-mail."
    )
    safe = html.escape(link, quote=True)
    body = (
        f"<p>Sign in to {html.escape(title)}:</p>"
        f'<p><a href="{safe}">Sign in</a></p>'
        f"<p>The link works once and expires in {minutes} minutes.<br>"
        "If you did not ask for it, ignore this e-mail.</p>"
    )
    return MailMessage(to=to, subject=f"Your sign-in link for {title}", text=text, html=body)


def send_magic_link(to: str, link: str) -> None:
    """Deliver a sign-in link. Blocking; call it off the event loop."""
    message = build_message(to, link)
    transport = settings.MAIL_TRANSPORT
    if transport == "console":
        from . import console

        console.send(message)
    elif transport == "smtp":
        from . import smtp

        smtp.send(message)
    elif transport == "mailgun":
        from . import mailgun

        mailgun.send(message)
    elif transport == "graph":
        from . import graph

        graph.send(message)
    else:
        raise RuntimeError("MAIL_TRANSPORT is not set; cannot send sign-in links.")
