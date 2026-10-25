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
