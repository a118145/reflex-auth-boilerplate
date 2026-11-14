"""The gate in front of ``POST /_upload``.

An upload is a plain HTTP request. Reflex turns it into an event for the
state named by the ``Reflex-Client-Token`` request header — a value that
lives in ``sessionStorage`` and in the WebSocket URL, so it is not a secret
and must not work as a credential. The event itself carries no handshake
headers, so the event middleware cannot see a cookie on it.

This ASGI middleware therefore checks the request, which does carry the
cookie: it must come from this app's pages and hold a live session. It then
records a *grant* — "client token X was shown session digest Y" — which
``AuthMiddleware`` requires before it lets a headerless event reach an app
handler. The upload runs only if the state behind the client token is signed
in with that very session.

The grant map holds digests only and lives in the process that received the
request, which is also the one that processes the upload event.

**Split origins.** Reflex's upload request does not send cookies cross-origin
(no ``withCredentials``). When the page and the backend are different origins
— ``reflex run`` in development, ports 3000 and 8000 — the cookie can never
arrive, so the gate cannot be enforced and stands aside. Production runs
``--single-port``, where it is enforced (``settings.public_url_problem``).
"""

from __future__ import annotations

import dataclasses
import time

import reflex as rx
from reflex.config import get_config
from reflex.constants import Endpoint
from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from ..utils.logging import get_logger
from . import security, service
from .cookie import COOKIE_NAME
from .origin import from_this_app, origin_of

log = get_logger(__name__)

# Whether the cookie can accompany an upload at all: same origin only.
ENFORCED = origin_of(get_config().api_url) == origin_of(get_config().frontend_url)

UPLOAD_PATH = get_config().prepend_backend_path(str(Endpoint.UPLOAD))

# The upload event is queued while the request is being read, but a small
# upload can be answered before the event is processed. A finished request's
# grant therefore stays valid this long.
GRACE_SECONDS = 30.0


@dataclasses.dataclass
class _Grant:
    token_hash: str
    active: int = 0  # requests in flight
    expires: float = 0.0  # monotonic; counts once no request is in flight


_grants: dict[str, _Grant] = {}


def lookup_session(token_hash: str) -> service.Identity | None:
    """The database read behind the check (tests replace it)."""
    with rx.session() as db:
        return service.resolve_session(db, token_hash)


def _open(client_token: str, token_hash: str) -> None:
    now = time.monotonic()
    for key in [k for k, g in _grants.items() if g.active == 0 and g.expires <= now]:
        del _grants[key]
    grant = _grants.get(client_token)
    if grant is None or grant.token_hash != token_hash:
        grant = _grants[client_token] = _Grant(token_hash)
    grant.active += 1


def _close(client_token: str, token_hash: str) -> None:
    grant = _grants.get(client_token)
    if grant is not None and grant.token_hash == token_hash:
        grant.active = max(grant.active - 1, 0)
        grant.expires = time.monotonic() + GRACE_SECONDS


def granted(client_token: str, token_hash: str) -> bool:
    """Whether a headerless event for ``client_token`` may run as the session
    with digest ``token_hash``. Always true where the gate cannot be enforced."""
    if not ENFORCED:
        return True
    grant = _grants.get(client_token)
    if grant is None or not token_hash or not client_token:
        return False
    live = grant.active > 0 or grant.expires > time.monotonic()
    return live and grant.token_hash == token_hash


class UploadGate:
    """ASGI middleware: uploads need this app's origin and a live session."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            not ENFORCED
            or scope["type"] != "http"
            or scope["method"] != "POST"
            or scope["path"].rstrip("/") != UPLOAD_PATH
        ):
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        if not from_this_app(request):
            await JSONResponse({"detail": "Cross-site request refused."}, 403)(scope, receive, send)
            return
        raw = request.cookies.get(COOKIE_NAME, "")
        client_token = request.headers.get("reflex-client-token", "")
        token_hash = security.token_hash(raw) if raw else ""
        identity = await run_in_threadpool(lookup_session, token_hash) if token_hash else None
        if identity is None or not client_token:
            log.info("auth.upload_refused", reason="no_session" if client_token else "no_token")
            await JSONResponse({"detail": "Sign in to upload."}, 401)(scope, receive, send)
            return

        _open(client_token, token_hash)
        try:
            await self.app(scope, receive, send)
        finally:
            _close(client_token, token_hash)
