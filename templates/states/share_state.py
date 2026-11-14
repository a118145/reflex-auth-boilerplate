"""Sharing what is open: its owner shares it with people and groups, or
makes it visible to everyone.

One state for everything shareable. The page's ``on_load`` names what is
open through a ``load_<kind>`` handler; the other handlers are the same for
every kind. A load fills this state only for the owner, every write carries
``share_owner_event``, and the service checks ownership again.

**A new shareable kind** gets one handler here, next to its ``Shareable`` in
``service/sharing.py``::

    if TYPE_CHECKING:
        note_id: str  # injected by the dynamic route — never assign it

    @rx.event
    @toast_errors
    async def load_note(self):
        await self._open(sharing.NOTES, self.note_id)

and its detail page lists that handler in ``on_load`` and shows
``rx.cond(ShareState.is_owner, share_card("..."))``. Add ``load_note`` to
``OPEN_TO_ANY_USER`` in ``tests/test_auth_policy.py``.
"""

from collections.abc import Callable
from typing import Any

import reflex as rx

from .. import service
from ..service import sharing
from ..service.sharing import Shareable
from ..auth.policy import share_owner_event
from ..components.toast import notify_error, notify_success
from ..utils.casting import as_id
from ..utils.logging import get_logger
from .handlers import call, toast_errors
from .people import actor_id, emails_for, user_by_email

log = get_logger(__name__).bind(state="ShareState")


class ShareState(rx.State):
    is_owner: bool = False
    shares: list[dict[str, str]] = []
    share_email: str = ""
    shared_with_all: bool = False
    group_shares: list[dict[str, str]] = []  # id, name — never members
    group_options: list[dict[str, str]] = []  # groups not yet shared with
    share_group: str = ""

    # What is open, set by a load and only for its owner. ``_kind`` names one of
    # ``sharing.KINDS``; "" means nothing is.
    _kind: str = ""
    _target_id: int | None = None
    _owner_id: int | None = None

    # The ``load_<kind>`` handlers go here — see the module docstring.

    async def _open(self, what: Shareable[Any], raw_id: str) -> None:
        # Forget the previous page first: its target must never be this
        # page's, whatever happens below.
        reset: Callable[[], None] = self.reset  # untyped in Reflex
        reset()
        me = await actor_id(self)
        try:
            await call(sharing.owned, what, me, as_id(raw_id))
        except (service.PermissionDeniedError, ValueError):
            # Not the owner (or no such thing): the card stays hidden.
            return
        self._kind, self._target_id, self._owner_id = what.kind, as_id(raw_id), me
        self.is_owner = True
        await self._refresh()

    def _what(self) -> tuple[Shareable[Any], int]:
        """What is open. Raises a refusal when nothing is — the handlers'
        check has passed by then, so that only happens across a page change."""
        kinds = {what.kind: what for what in sharing.KINDS}
        if self._kind not in kinds or self._target_id is None:
            raise service.PermissionDeniedError("Nothing is open to share.")
        return kinds[self._kind], self._target_id

    async def _refresh(self) -> None:
        what, target_id = self._what()
        shares = await call(sharing.shares_of, what, await actor_id(self), target_id)
        groups = await call(service.group_list)
        people = await call(emails_for, shares.users)
        share_ids, group_ids = shares.users, shares.groups
        self.shares = [{"id": str(u), "email": people.get(u, f"#{u}")} for u in share_ids]
        self.shared_with_all = shares.shared_with_all
        rows = [{"id": str(g.id), "name": g.name} for g in groups]
        self.group_shares = [r for r in rows if int(r["id"]) in group_ids]
        self.group_options = [r for r in rows if int(r["id"]) not in group_ids]

    @share_owner_event
    def set_share_email(self, value: str):
        self.share_email = value

    @share_owner_event
    @toast_errors
    async def add_share(self):
        what, target_id = self._what()
        me = await actor_id(self)
        user_id = await call(user_by_email, self.share_email)
        if user_id is None:
            return notify_error("Unknown address: the person must have signed in once.")
        await call(sharing.share_with_user, what, me, target_id, user_id)
        log.info(f"{what.kind}.share", target_id=target_id, user_id=user_id)
        self.share_email = ""
        await self._refresh()
        return notify_success("Shared.")

    @share_owner_event
    @toast_errors
    async def remove_share(self, user_id: str):
        what, target_id = self._what()
        me = await actor_id(self)
        await call(sharing.unshare_user, what, me, target_id, as_id(user_id))
        log.info(f"{what.kind}.unshare", target_id=target_id, user_id=user_id)
        await self._refresh()

    @share_owner_event
    def set_share_group(self, value: str):
        self.share_group = value

    @share_owner_event
    @toast_errors
    async def add_group_share(self):
        if not self.share_group:
            return notify_error("Pick a group.")
        what, target_id = self._what()
        me = await actor_id(self)
        await call(sharing.share_with_group, what, me, target_id, as_id(self.share_group))
        log.info(f"{what.kind}.share_group", target_id=target_id, group_id=self.share_group)
        self.share_group = ""
        await self._refresh()
        return notify_success("Shared with the group.")

    @share_owner_event
    @toast_errors
    async def remove_group_share(self, group_id: str):
        what, target_id = self._what()
        me = await actor_id(self)
        await call(sharing.unshare_group, what, me, target_id, as_id(group_id))
        log.info(f"{what.kind}.unshare_group", target_id=target_id, group_id=group_id)
        await self._refresh()

    @share_owner_event
    @toast_errors
    async def set_shared_with_all(self, value: bool):
        what, target_id = self._what()
        me = await actor_id(self)
        await call(sharing.set_shared_with_all, what, me, target_id, value)
        self.shared_with_all = value
        log.info(f"{what.kind}.share_all", target_id=target_id, shared=value)
