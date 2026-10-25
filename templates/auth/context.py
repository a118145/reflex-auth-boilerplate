"""The object an authorization check receives.

Its own module so ``authz`` (the checks) and ``policy`` (where checks are
attached) can both import it without importing each other.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Awaitable, Callable, Mapping
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from reflex.state import BaseState

    from .service import Identity


@dataclasses.dataclass(frozen=True)
class AuthContext:
    """What a check sees. Only built for a signed-in user — a check never
    runs for an anonymous caller."""

    identity: Identity
    route: str
    event_name: str
    payload: Mapping[str, Any]
    # The root state, for async checks that read another state:
    # ``await ctx.state.get_state(SomeState)``.
    state: BaseState


AuthCheck = Callable[[AuthContext], bool | Awaitable[bool]]
AuthValue = bool | AuthCheck
