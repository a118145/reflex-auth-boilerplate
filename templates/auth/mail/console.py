"""Development transport: writes the link to the server log.

Never to the browser — the link is a credential, and the UI shows the same
"check your inbox" message whatever happened. ``settings`` refuses this
transport when ``REFLEX_ENV_MODE=prod``.
"""

from ...utils.logging import get_logger
from .message import MailMessage

log = get_logger(__name__)


def send(message: MailMessage) -> None:
    log.warning("mail.console", to=message.to, subject=message.subject, body=message.text)
