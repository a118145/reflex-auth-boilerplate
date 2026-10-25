"""The gate in front of every event.

Registered at index 0 with ``app.add_middleware(AuthMiddleware(), index=0)``,
so it runs before Reflex computes any delta. For each event it:

1. **Takes the session cookie out of the router data.** Reflex copies the
   WebSocket handshake headers — ``cookie`` included — into ``State.router``
   and serialises them to the browser with every delta. An HttpOnly cookie
   would be readable from JavaScript through the state. The cookie is
   removed before that can happen; only its digest is kept, in a private var.
2. **Resolves the session** against the database when the cookie changed,
   on every page load, and otherwise at most every
   ``AUTH_SESSION_RECHECK_SECONDS`` (60), so a revoked session or a blocked
   account stops working within that time.
3. **Resets every app state when the signed-in user changes**, so one
   user's data cannot be shown to the next on the same browser tab.
4. **Applies ``auth.policy``** — page loads by route, handlers by their
   ``auth_event`` policy (login required unless opted out).
"""

from __future__ import annotations

import time
import urllib.parse
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import reflex as rx
from reflex.event import Event
from reflex.istate.data import RouterData
from reflex.middleware.middleware import Middleware
from reflex.state import OnLoadInternalState, StateUpdate

from ..components.toast import notify_error
from ..navigation import routes
from ..utils.logging import get_logger
from . import security, service, settings
from .context import AuthContext
from .cookie import COOKIE_NAME
from .policy import PUBLIC_ROUTES, ROUTE_CHECKS, handler_policy, run_check
from .state import AuthState

if TYPE_CHECKING:
    from reflex.app import App
    from reflex.state import BaseState

log = get_logger(__name__)

_PAGE_LOAD_EVENT = f"{OnLoadInternalState.get_full_name()}.on_load_internal"


# Set on router data whose cookie was already taken out. ``router_data``
# itself never reaches the client (``is_var=False``), but events that Reflex
# chains on the backend (the page's ``on_load`` handlers, a handler's returned
# events) are built from the state's stored, already-stripped copy. Without
# this flag the missing cookie in such a copy would read as "signed out".
# A client that sends the key itself only gets to keep its *own* current
# identity, which is still re-checked against the database on every page
# load and at least every AUTH_SESSION_RECHECK_SECONDS — so it grants nothing.
_STRIPPED = "_auth_cookie_stripped"


def take_session_cookie(router_data: dict[str, Any]) -> str | None:
    """Remove the session cookie from ``router_data`` in place; return its value.

    ``None`` means this event says nothing about the cookie (no handshake
    headers, or a copy that was stripped before), so the previous identity
    stands. ``""`` means the browser sent no session cookie: signed out.
    """
    headers = router_data.get("headers")
    if router_data.get(_STRIPPED) or not isinstance(headers, dict):
        return None
    kept: list[str] = []
    value = ""
    for part in str(headers.get("cookie", "")).split(";"):
        name, sep, raw = part.strip().partition("=")
        if not sep:
            continue
        if name == COOKIE_NAME:
            value = raw
        else:
            kept.append(f"{name}={raw}")
    headers["cookie"] = "; ".join(kept)
    router_data[_STRIPPED] = True
    return value


def lookup_session(token_hash: str) -> service.Identity | None:
    """The database read behind every session check (tests replace it)."""
    with rx.session() as db:
        return service.resolve_session(db, token_hash)


def _is_framework_state(cls: type[BaseState]) -> bool:
    return cls.__module__.split(".")[0] in ("reflex", "reflex_base")


def _app_state_classes(root: type[BaseState]) -> list[type[BaseState]]:
    found: list[type[BaseState]] = []
    pending = list(root.get_substates())
    while pending:
        cls = pending.pop()
        pending.extend(cls.get_substates())
        if not _is_framework_state(cls) and cls is not AuthState:
            found.append(cls)
    return found


class AuthMiddleware(Middleware):
    async def preprocess(self, app: App, state: BaseState, event: Event) -> StateUpdate | None:
        raw = take_session_cookie(event.router_data)
        if raw is not None:
            # The headers dict was edited in place; rebuild the derived router
            # object so the cookie is gone from what gets serialised.
            state.router = RouterData.from_router_data(state.router_data)

        auth = await state.get_state(AuthState)
        await self._sync_identity(state, auth, raw, force=event.name == _PAGE_LOAD_EVENT)
        identity = auth._identity()

        if event.name == _PAGE_LOAD_EVENT:
            return await self._gate_page(state, identity)

        try:
            cls = event.state_cls
        except KeyError:
            log.warning("auth.unknown_event", event_name=event.name)
            return _deny_update("Action not allowed")
        if _is_framework_state(cls):
            return None  # hydrate, client storage sync, … — carry no app data

        handler = cls.event_handlers.get(event.name.rpartition(".")[2])
        policy = handler_policy(handler.fn if handler is not None else None)
        if policy is False:
            return None
        if identity is None:
            return _login_redirect(state)
        if policy is True:
            return None
        ctx = AuthContext(
            identity=identity,
            route=state.router.route_id,
            event_name=event.name,
            payload=event.payload,
            state=state,
        )
        if await run_check(policy, ctx):
            return None
        log.info("auth.event_denied", event_name=event.name, user_id=identity.user_id)
        return _deny_update("Action not allowed")

    async def _sync_identity(
        self, root: BaseState, auth: AuthState, raw: str | None, *, force: bool
    ) -> None:
        token_hash = auth._token_hash if raw is None else (security.token_hash(raw) if raw else "")
        fresh = time.time() - auth._checked_at < settings.SESSION_RECHECK.total_seconds()
        if token_hash == auth._token_hash and fresh and not force:
            return
        identity = lookup_session(token_hash) if token_hash else None
        previous_user = auth._user_id
        auth._apply(token_hash, identity, time.time())
        if previous_user is not None and previous_user != (identity.user_id if identity else None):
            await _reset_app_states(root)
            log.info("auth.states_reset", previous_user_id=previous_user)

    async def _gate_page(
        self, state: BaseState, identity: service.Identity | None
    ) -> StateUpdate | None:
        route = state.router.route_id
        if route in PUBLIC_ROUTES:
            return None
        if identity is None:
            return _login_redirect(state)
        check = ROUTE_CHECKS.get(route)
        if check is None:
            return None
        ctx = AuthContext(
            identity=identity, route=route, event_name=_PAGE_LOAD_EVENT, payload={}, state=state
        )
        if await run_check(check, ctx):
            return None
        log.info("auth.page_denied", route=route, user_id=identity.user_id)
        return StateUpdate(events=Event.from_event_type(rx.redirect(routes.FORBIDDEN_ROUTE)))


async def _reset_app_states(root: BaseState) -> None:
    for cls in _app_state_classes(type(root)):
        substate = await root.get_state(cls)
        reset: Callable[[], None] = substate.reset  # untyped in Reflex
        reset()


def _login_redirect(state: BaseState) -> StateUpdate:
    url = state.router.url
    here = url.path + (f"?{url.query}" if url.query else "")
    target = routes.LOGIN_ROUTE
    if security.safe_redirect_path(here, "") not in ("", routes.LOGIN_ROUTE, "/"):
        target += "?" + urllib.parse.urlencode({"redirect_to": here})
    return StateUpdate(events=Event.from_event_type(rx.redirect(target)))


def _deny_update(message: str) -> StateUpdate:
    return StateUpdate(events=Event.from_event_type(notify_error(message)))
