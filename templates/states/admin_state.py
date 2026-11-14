"""Admin area: accounts, groups, sessions, audit log.

Every handler carries ``auth=is_admin``. That is the enforcement — the admin
menu entry being hidden from others is only presentation. Rendering the rows
is fine: they only reach a client whose admin check passed, because they are
loaded exclusively by these handlers, and the middleware resets this state
when the signed-in user changes.
"""

from collections.abc import Callable
from typing import Any

import reflex as rx
from pydantic import BaseModel, Field
from sqlmodel import Session

from .. import service as core

from ..auth import service
from ..auth.policy import admin_event
from ..auth.state import AuthState
from ..components.toast import notify_error, notify_success
from ..utils.casting import as_id
from ..utils.logging import get_logger
from ..utils.validation import parse_form
from .handlers import call, toast_errors

log = get_logger(__name__).bind(state="AdminState")


class GroupName(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class AdminState(rx.State):
    users: list[service.UserRow] = []
    sessions: list[service.SessionRow] = []
    audit: list[service.AuditRow] = []

    # Dashboard counts; "—" until the admin-only load has run.
    user_count: str = "—"
    session_count: str = "—"
    audit_week_count: str = "—"
    group_count: str = "—"

    groups: list[core.GroupRow] = []
    # Open dialog: "new", "rename" or "delete" (both of group_id), "" = none.
    group_dialog: str = ""
    group_id: int | None = None
    # Members dialog of group_id.
    members_open: bool = False
    member_ids: list[int] = []
    member_pick: str = ""

    # Block / unblock confirmation.
    block_open: bool = False
    block_user_id: int | None = None
    block_target_blocked: bool = True

    # Merge dialog: the row it was opened on is the source; the admin picks
    # the target, which survives.
    merge_open: bool = False
    merge_source_id: int | None = None
    merge_target_id: str = ""
    # The same dialog deletes the source instead; the pick takes over its data.
    delete_mode: bool = False

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
    def group_label(self) -> str:
        return next((g.name for g in self.groups if g.id == self.group_id), "")

    @rx.var
    def member_rows(self) -> list[service.UserRow]:
        return [u for u in self.users if u.id in self.member_ids]

    @rx.var
    def member_candidates(self) -> list[service.UserRow]:
        return [u for u in self.users if u.id not in self.member_ids and not u.blocked]

    @rx.var
    def block_label(self) -> str:
        return next((u.emails for u in self.users if u.id == self.block_user_id), "")

    async def _actor_id(self) -> int:
        auth = await self.get_state(AuthState)
        identity = auth._identity()
        assert identity is not None  # is_admin passed, so someone is signed in
        return identity.user_id

    @admin_event
    @toast_errors
    async def load_dashboard(self) -> None:
        counts = await call(service.admin_counts)
        self.group_count = str(len(await call(core.group_list)))
        self.user_count = str(counts.users)
        self.session_count = str(counts.live_sessions)
        self.audit_week_count = str(counts.audit_last_week)

    @admin_event
    @toast_errors
    async def load_users(self) -> None:
        self.users = await call(service.list_users)

    @admin_event
    @toast_errors
    async def load_sessions(self) -> None:
        self.sessions = await call(service.list_sessions)

    @admin_event
    @toast_errors
    async def load_audit(self) -> None:
        self.audit = await call(service.list_audit)

    @admin_event
    def ask_block(self, user_id: int, blocked: bool) -> None:
        self.block_user_id = user_id
        self.block_target_blocked = blocked
        self.block_open = True

    @admin_event
    def set_block_open(self, value: bool) -> None:
        self.block_open = value

    @admin_event
    @toast_errors
    async def confirm_block(self) -> Any:
        self.block_open = False
        if self.block_user_id is None:
            return None
        await call(
            service.set_blocked,
            self.block_user_id,
            self.block_target_blocked,
            actor_user_id=await self._actor_id(),
        )
        done = "Blocked" if self.block_target_blocked else "Unblocked"
        return [AdminState.load_users, notify_success(f"{done} {self.block_label}.")]

    @admin_event
    def open_merge(self, source_id: int, delete_mode: bool) -> None:
        self.merge_source_id = source_id
        self.merge_target_id = ""
        self.delete_mode = delete_mode
        self.merge_open = True

    @admin_event
    def set_merge_open(self, value: bool) -> None:
        self.merge_open = value

    @admin_event
    def set_merge_target(self, value: str) -> None:
        self.merge_target_id = value

    @admin_event
    @toast_errors
    async def confirm_merge(self) -> Any:
        if self.merge_source_id is None or not self.merge_target_id.isdigit():
            return notify_error("Pick the account to merge into.")
        await call(
            service.merge_users,
            self.merge_source_id,
            as_id(self.merge_target_id),
            actor_user_id=await self._actor_id(),
        )
        self.merge_open = False
        return [
            AdminState.load_users,
            notify_success("Accounts merged. Both were signed out everywhere."),
        ]

    @admin_event
    @toast_errors
    async def confirm_delete(self) -> Any:
        if self.merge_source_id is None or not self.merge_target_id.isdigit():
            return notify_error("Pick the new owner.")
        await call(
            service.delete_user,
            self.merge_source_id,
            as_id(self.merge_target_id),
            actor_user_id=await self._actor_id(),
        )
        self.merge_open = False
        return [AdminState.load_users, notify_success("Account deleted; its data was handed over.")]

    @admin_event
    @toast_errors
    async def revoke(self, session_id: int) -> Any:
        await call(service.revoke_session, session_id, actor_user_id=await self._actor_id())
        return [AdminState.load_sessions, notify_success("Session ended.")]

    @admin_event
    @toast_errors
    async def load_groups(self) -> None:
        self.groups = await call(core.group_rows)

    @admin_event
    def new_group(self) -> None:
        self.group_dialog, self.group_id = "new", None

    @admin_event
    def ask_rename_group(self, group_id: int) -> None:
        self.group_dialog, self.group_id = "rename", group_id

    @admin_event
    def close_group_dialog(self) -> None:
        self.group_dialog = ""

    @admin_event
    @toast_errors
    async def submit_group_name(self, form_data: dict[str, Any]) -> Any:
        """Create or rename; on an error the dialog stays open with the input."""
        form, errors = parse_form(form_data, GroupName)
        if form is None:
            return notify_error("; ".join(errors.values()))
        actor, group_id = await self._actor_id(), self.group_id
        if self.group_dialog == "rename" and group_id is not None:
            await call(core.rename_group, actor, group_id, form.name)
            event, done = "group.rename", "Group renamed."
        else:
            group_id = (await call(core.create_group, actor, form.name)).id
            event, done = "group.create", "Group created."
        log.info(event, group_id=group_id)
        self.group_dialog = ""
        return [AdminState.load_groups, notify_success(done)]

    @admin_event
    def ask_delete_group(self, group_id: int) -> None:
        self.group_dialog, self.group_id = "delete", group_id

    @admin_event
    @toast_errors
    async def confirm_delete_group(self) -> Any:
        self.group_dialog = ""
        if self.group_id is None:
            return None
        await call(core.delete_group, await self._actor_id(), self.group_id)
        log.info("group.delete", group_id=self.group_id)
        return [AdminState.load_groups, notify_success(f'Deleted group "{self.group_label}".')]

    async def _load_members(self) -> None:
        self.users = await call(service.list_users)
        self.member_ids = await call(core.group_members, self.group_id) if self.group_id else []

    @admin_event
    @toast_errors
    async def open_members(self, group_id: int) -> None:
        self.group_id, self.member_pick, self.members_open = group_id, "", True
        await self._load_members()

    @admin_event
    def set_members_open(self, value: bool) -> None:
        self.members_open = value

    @admin_event
    def set_member_pick(self, value: str) -> None:
        self.member_pick = value

    @admin_event
    @toast_errors
    async def add_member(self) -> Any:
        if not self.member_pick.isdigit():
            return notify_error("Pick a person to add.")
        return await self._change_member(
            core.add_member, as_id(self.member_pick), "group.member_add"
        )

    @admin_event
    @toast_errors
    async def remove_member(self, user_id: int) -> Any:
        return await self._change_member(core.remove_member, user_id, "group.member_remove")

    async def _change_member(
        self, change: Callable[[Session, int, int, int], None], user_id: int, event: str
    ) -> Any:
        if self.group_id is None:
            return None
        await call(change, await self._actor_id(), self.group_id, user_id)
        log.info(event, group_id=self.group_id, user_id=user_id)
        self.member_pick = ""
        await self._load_members()
        return AdminState.load_groups
