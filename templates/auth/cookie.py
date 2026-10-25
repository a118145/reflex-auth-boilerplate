"""The session cookie: the only place the session token lives on the client.

``HttpOnly`` (no JavaScript access), ``SameSite=Lax`` (not sent on cross-site
POSTs, which is what makes the logout and login forms CSRF-safe together with
the origin check in ``endpoints``), ``Path=/``. Over HTTPS it is also
``Secure`` and carries the ``__Host-`` prefix, which pins it to exactly this
host. The scheme is taken from ``api_url`` because the backend sets it.
"""

from reflex.config import get_config
from starlette.responses import Response

from . import settings

SECURE = get_config().api_url.startswith("https://")
COOKIE_NAME = ("__Host-" if SECURE else "") + f"{get_config().app_name}_session"


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=int(settings.SESSION_EXPIRATION.total_seconds()),
        path="/",
        secure=SECURE,
        httponly=True,
        samesite="lax",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, path="/", secure=SECURE, httponly=True, samesite="lax")
