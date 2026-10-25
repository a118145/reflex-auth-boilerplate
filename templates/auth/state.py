"""``AuthState`` — who is signed in, for rendering.

Like ``NavState`` this lives outside ``states/``: it belongs to the auth
package and is written only by ``auth.middleware``, which resolves the
session cookie on every event before any handler runs.

**Nothing secret is a public var.** The session token never enters any state:
the browser holds it in an HttpOnly cookie, the middleware strips it from the
router data that Reflex would otherwise serialise to the client, and only its
SHA-256 digest is kept here, in a private (``_``) var that never leaves the
backend. The public vars below are display values — the same things the page
would show anyway. Enforcement never reads them; it reads the private
identity through ``auth.policy``.
"""

import asyncio
from typing import Any

import reflex as rx
from reflex.config import get_config

from ..navigation import routes
from ..utils.logging import get_logger
from . import security, service
from .mail.message import send_magic_link
from .policy import auth_event

log = get_logger(__name__).bind(state="AuthState")

ENDPOINT_PREFIX = "/_auth"


def backend_url(path: str) -> str:
    """Absolute URL of an auth endpoint. The endpoints live on the backend,
    which is ``api_url`` — the same origin as the page with ``--single-port``,
    port 8000 next to the dev server's 3000 otherwise."""
    return get_config().api_url.rstrip("/") + ENDPOINT_PREFIX + path


def frontend_url(path: str) -> str:
    base = (get_config().deploy_url or "").rstrip("/")
    return base + path


class AuthState(rx.State):
    # Display only.
    is_authenticated: bool = False
    is_admin: bool = False
    user_email: str = ""

    # Login form feedback.
    link_sent: bool = False
    form_error: str = ""

    # Backend only. The digest of the session cookie, and what it resolved
    # to when last checked against the database.
    _token_hash: str = ""
    _checked_at: float = 0.0
    _session_id: int | None = None
    _user_id: int | None = None
    _admin: bool = False

    @rx.var
    def login_redirect_to(self) -> str:
        """Where to go after signing in — validated again on the backend."""
        return self.router.url.query_parameters.get("redirect_to", "")

    @rx.var
    def login_error(self) -> str:
        """Error code a login endpoint redirected back with, if any."""
        return self.router.url.query_parameters.get("error", "")

    def _identity(self) -> service.Identity | None:
        if self._session_id is None or self._user_id is None:
            return None
        return service.Identity(
            session_id=self._session_id,
            user_id=self._user_id,
            email=self.user_email,
            is_admin=self._admin,
        )

    def _apply(self, token_hash: str, identity: service.Identity | None, checked_at: float) -> None:
        self._token_hash = token_hash
        self._checked_at = checked_at
        self._session_id = identity.session_id if identity else None
        self._user_id = identity.user_id if identity else None
        self._admin = identity.is_admin if identity else False
        self.is_authenticated = identity is not None
        self.is_admin = self._admin
        self.user_email = identity.email if identity else ""

    def _client_ip(self) -> str:
        headers = self.router.headers.raw_headers
        return security.client_ip(
            headers.get("asgi-scope-client", ""), headers.get("x-forwarded-for")
        )

    @auth_event(auth=False)
    def leave_public_page(self) -> Any:
        """``on_load`` of the login pages: a signed-in user has no business
        there, so send them on."""
        self.link_sent = False
        self.form_error = ""
        if self.is_authenticated:
            target = self.router.url.query_parameters.get("redirect_to")
            return rx.redirect(security.safe_redirect_path(target, routes.HOME_ROUTE))
        return None

    @auth_event(auth=False)
    def request_link(self, form_data: dict[str, Any]) -> None:
        raw_email = str(form_data.get("email", ""))
        if security.normalize_email(raw_email) is None:
            self.form_error = "Enter a valid e-mail address."
            return
        redirect_to = security.safe_redirect_path(
            str(form_data.get("redirect_to") or ""), routes.HOME_ROUTE
        )
        with rx.session() as db:
            token, _outcome = service.request_link(
                db, raw_email, client_ip=self._client_ip(), redirect_to=redirect_to
            )
        if token is not None:
            email = security.normalize_email(raw_email) or raw_email
            link = backend_url(f"/link?t={token}")
            # Sent off the event loop, and not awaited: whether an address
            # gets a mail must not show in how long this handler takes.
            future = asyncio.get_running_loop().run_in_executor(None, send_magic_link, email, link)
            future.add_done_callback(_log_send_failure)
        # One answer for every outcome, so the form cannot be used to find
        # out which addresses have accounts, are blocked or are allowed.
        self.form_error = ""
        self.link_sent = True

    @auth_event(auth=False)
    def reset_login_form(self) -> None:
        self.link_sent = False
        self.form_error = ""


def _log_send_failure(future: "asyncio.Future[None]") -> None:
    if (error := future.exception()) is not None:
        log.error("mail.send_failed", error=repr(error))
