"""Admin area: accounts, sessions, audit log.

Every handler carries ``auth=is_admin``. That is the enforcement — the admin
menu entry being hidden from others is only presentation. Rendering the rows
is fine: they only reach a client whose admin check passed, because they are
loaded exclusively by these handlers, and the middleware resets this state
when the signed-in user changes.
"""

from typing import Any

import reflex as rx

from ..auth import service
from ..auth.authz import is_admin
from ..auth.policy import auth_event
from ..auth.state import AuthState
from ..components.toast import notify_error, notify_success

admin_event = auth_event(auth=is_admin)


class AdminState(rx.State):
    users: list[service.UserRow] = []
    sessions: list[service.SessionRow] = []
    audit: list[service.AuditRow] = []

    # Block / unblock confirmation.
    block_open: bool = False
    block_user_id: int | None = None
    block_target_blocked: bool = True

    # Merge dialog: the row it was opened on is the source; the admin picks
    # the target, which survives.
    merge_open: bool = False
    merge_source_id: int | None = None
    merge_target_id: str = ""

    @rx.var
    def merge_source_label(self) -> str:
        return next((u.emails for u in self.users if u.id == self.merge_source_id), "")

    @rx.var
    def merge_candidates(self) -> list[service.UserRow]:
        return [
            u
            for u in self.users
            if u.id != self.merge_source_id and not u.is_admin and not u.blocked
        ]

    @rx.var
    def block_label(self) -> str:
        return next((u.emails for u in self.users if u.id == self.block_user_id), "")

    async def _actor_id(self) -> int:
        auth = await self.get_state(AuthState)
        identity = auth._identity()
        assert identity is not None  # is_admin passed, so someone is signed in
        return identity.user_id

    @admin_event
    def load_users(self) -> None:
        with rx.session() as db:
            self.users = service.list_users(db)

    @admin_event
    def load_sessions(self) -> None:
        with rx.session() as db:
            self.sessions = service.list_sessions(db)

    @admin_event
    def load_audit(self) -> None:
        with rx.session() as db:
            self.audit = service.list_audit(db)

    @admin_event
    def ask_block(self, user_id: int, blocked: bool) -> None:
        self.block_user_id = user_id
        self.block_target_blocked = blocked
        self.block_open = True

    @admin_event
    def set_block_open(self, value: bool) -> None:
        self.block_open = value

    @admin_event
    async def confirm_block(self) -> Any:
        self.block_open = False
        if self.block_user_id is None:
            return None
        try:
            with rx.session() as db:
                service.set_blocked(
                    db,
                    self.block_user_id,
                    self.block_target_blocked,
                    actor_user_id=await self._actor_id(),
                )
        except service.AdminActionError as error:
            return notify_error(str(error))
        done = "Blocked" if self.block_target_blocked else "Unblocked"
        return [AdminState.load_users, notify_success(f"{done} {self.block_label}.")]

    @admin_event
    def open_merge(self, source_id: int) -> None:
        self.merge_source_id = source_id
        self.merge_target_id = ""
        self.merge_open = True

    @admin_event
    def set_merge_open(self, value: bool) -> None:
        self.merge_open = value

    @admin_event
    def set_merge_target(self, value: str) -> None:
        self.merge_target_id = value

    @admin_event
    async def confirm_merge(self) -> Any:
        if self.merge_source_id is None or not self.merge_target_id.isdigit():
            return notify_error("Pick the account to merge into.")
        try:
            with rx.session() as db:
                service.merge_users(
                    db,
                    self.merge_source_id,
                    int(self.merge_target_id),
                    actor_user_id=await self._actor_id(),
                )
        except service.AdminActionError as error:
            return notify_error(str(error))
        self.merge_open = False
        return [
            AdminState.load_users,
            notify_success("Accounts merged. Both were signed out everywhere."),
        ]

    @admin_event
    async def revoke(self, session_id: int) -> Any:
        try:
            with rx.session() as db:
                service.revoke_session(db, session_id, actor_user_id=await self._actor_id())
        except service.AdminActionError as error:
            return notify_error(str(error))
        return [AdminState.load_sessions, notify_success("Session ended.")]
