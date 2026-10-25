"""Who may reach what — the one place authorization is declared.

Modelled on Reflex Enterprise's secure-by-default auth: everything requires a
signed-in user unless it is opted out here, and finer rules are callable
checks attached to the surface they protect, never ``if`` statements inside
handlers.

* **Pages** — every route requires login except ``PUBLIC_ROUTES``. A route in
  ``ROUTE_CHECKS`` additionally runs that check; a signed-in user who fails it
  is sent to ``/forbidden``. New pages are protected without doing anything.
* **Event handlers** — every handler on an app state requires login.
  ``@auth_event(auth=False)`` makes one public, ``@auth_event(auth=check)``
  restricts it; a failed check blocks the handler with an "Action not
  allowed" toast. A plain ``@rx.event`` is the same as ``auth=True``.
* **State fields** — by convention: load protected data only in protected
  handlers (``on_load`` included), give fields presentable defaults, and the
  middleware resets every app state when the signed-in user changes.

Hiding a control is not enforcement: anything rendered conditionally on
``AuthState.is_admin`` must also have its handler checked here.
"""

import inspect
from collections.abc import Callable
from typing import Any, overload

import reflex as rx
from reflex.event import EventCallback
from reflex.state import BaseState

from ..navigation import routes
from ..utils.logging import get_logger
from . import authz
from .context import AuthCheck, AuthContext, AuthValue

log = get_logger(__name__)


AUTH_ATTR = "_auth_policy"


@overload
def auth_event[S: BaseState, *P](fn: Callable[[S, *P], Any], /) -> EventCallback[*P]: ...
@overload
def auth_event[S: BaseState, *P](
    *, auth: AuthValue = True, **event_kwargs: Any
) -> Callable[[Callable[[S, *P], Any]], EventCallback[*P]]: ...
def auth_event(fn: Any = None, /, *, auth: AuthValue = True, **event_kwargs: Any) -> Any:
    """``rx.event`` plus an authorization policy. Use instead of ``@rx.event``.

    Bare (``@auth_event``) or called (``@auth_event(auth=...)``); other keyword
    arguments are passed to ``rx.event``, and the overloads mirror its typing.
    ``auth=True`` (default) — signed-in users; ``auth=False`` — everyone;
    ``auth=check`` — signed-in users for whom ``check(ctx)`` is truthy. A check
    that raises denies (fails closed).
    """

    def wrap(f: Callable[..., Any]) -> Any:
        setattr(f, AUTH_ATTR, auth)
        handler: Any = rx.event(f, **event_kwargs) if event_kwargs else rx.event(f)
        setattr(handler, AUTH_ATTR, auth)
        return handler

    return wrap(fn) if fn is not None else wrap


def handler_policy(fn: Callable[..., Any] | None) -> AuthValue:
    """The policy of an event handler function; undecorated means login."""
    return getattr(fn, AUTH_ATTR, True) if fn is not None else True


async def run_check(check: AuthCheck, ctx: AuthContext) -> bool:
    try:
        result = check(ctx)
        if inspect.isawaitable(result):
            result = await result
        return bool(result)
    except Exception:
        log.exception("auth.check_failed", check=getattr(check, "__name__", repr(check)))
        return False


# Reachable without signing in. Keep this list short and every entry
# deliberate; ``tests/test_auth_policy.py`` pins it.
PUBLIC_ROUTES: frozenset[str] = frozenset(
    {
        routes.LOGIN_ROUTE,
        routes.ADMIN_LOGIN_ROUTE,
        routes.FORBIDDEN_ROUTE,
    }
)

# Routes that need more than a signed-in user.
ROUTE_CHECKS: dict[str, AuthCheck] = {
    routes.ADMIN_ROUTE: authz.is_admin,
    routes.ADMIN_SESSIONS_ROUTE: authz.is_admin,
    routes.ADMIN_AUDIT_ROUTE: authz.is_admin,
}
