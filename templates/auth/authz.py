"""Authorization checks. Attach them with ``auth=``, never call them in a handler.

A check takes an ``AuthContext`` and returns a bool (or an awaitable of one).
It runs only for a signed-in user, and a check that raises denies. Name each
one for the question it answers.

Keep checks cheap: one runs on every gated event. If a check needs data from
the database, load it into a state once (in an ``on_load``) and read that
state here via ``await ctx.state.get_state(...)``.
"""

from .context import AuthContext


def is_admin(ctx: AuthContext) -> bool:
    """The admin, signed in with the password. A magic-link session never is,
    even for an address of the admin account."""
    return ctx.identity.is_admin


# --- Ownership. The pattern for "the signed-in user owns what is open": the
# page's on_load asks the service for the thing (which only ever returns what
# the user may see) and keeps its owner id in a private state var; the check
# compares it with the signed-in user. That makes a check cheap — no query per
# event — and it is a *pre-filter*: it produces the "Action not allowed" toast
# and keeps handlers honest, while the service checks ownership again on every
# write, with the acting user's id. Add one ``owns_open_<thing>`` per state
# that holds such a thing, and a named decorator for it in ``policy.py``.


async def owns_open_share_target(ctx: AuthContext) -> bool:
    """The signed-in user owns what is open in ShareState (its page's
    on_load says what that is)."""
    from ..states.share_state import ShareState  # lazy: states import policy

    state = await ctx.state.get_state(ShareState)
    return state._owner_id is not None and state._owner_id == ctx.identity.user_id
