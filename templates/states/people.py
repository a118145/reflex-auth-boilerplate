"""Who is acting, and how people are shown.

Handlers get the acting user's id from ``actor_id`` — the identity the auth
middleware resolved for this event, never anything the browser sent. People
are shown by their first e-mail address and found by any of them: those
lookups are ``auth/directory.py``'s, re-exported here.
"""

import reflex as rx

from ..auth.directory import emails_for, user_by_email
from ..auth.state import AuthState

__all__ = ["actor_id", "emails_for", "user_by_email"]


async def actor_id(state: rx.State) -> int:
    """The signed-in user's id. Every caller sits behind the auth gate, so
    there always is one; a missing identity is a bug, not a user error."""
    auth = await state.get_state(AuthState)
    identity = auth._identity()
    if identity is None:
        raise PermissionError("not signed in")
    return identity.user_id
