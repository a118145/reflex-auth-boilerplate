"""Admin: groups — create, rename, delete, members. Route gated by ``authz.is_admin``."""

import reflex as rx
from reflex.event import EventSpec

from ..auth.service import UserRow
from ..components.admin import admin_page
from ..components.confirm_dialog import confirm_dialog
from ..navigation import routes
from ..service import GroupRow
from ..states.admin_state import AdminState
from ..ui.base import base_page


def _small(label: str, on_click: EventSpec, **props: str) -> rx.Component:
    return rx.button(label, size="1", variant="soft", on_click=on_click, **props)


def _row(group: GroupRow) -> rx.Component:
    return rx.table.row(
        rx.table.row_header_cell(group.name),
        rx.table.cell(group.members.to_string()),
        rx.table.cell(
            rx.hstack(
                _small("Members…", AdminState.open_members(group.id)),
                _small("Rename…", AdminState.ask_rename_group(group.id)),
                _small("Delete…", AdminState.ask_delete_group(group.id), color_scheme="red"),
                spacing="3",
            )
        ),
    )


def _name_dialog() -> rx.Component:
    renaming = AdminState.group_dialog == "rename"
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title(rx.cond(renaming, "Rename group", "New group")),
            rx.form(
                rx.vstack(
                    rx.input(
                        name="name",
                        default_value=rx.cond(renaming, AdminState.group_label, ""),
                        placeholder="Name",
                        auto_focus=True,
                        width="100%",
                    ),
                    rx.hstack(
                        rx.dialog.close(rx.button("Cancel", variant="soft", color_scheme="gray")),
                        rx.button("Save", type="submit"),
                        justify="end",
                        spacing="3",
                        width="100%",
                    ),
                    spacing="3",
                ),
                on_submit=AdminState.submit_group_name,
                reset_on_submit=False,
            ),
            max_width="24em",
        ),
        open=(AdminState.group_dialog == "new") | renaming,
        on_open_change=lambda _: AdminState.close_group_dialog(),
    )


def _member(user: UserRow) -> rx.Component:
    return rx.hstack(
        rx.text(user.emails, title=user.emails, truncate=True, min_width="0"),
        rx.spacer(),
        _small("Remove", AdminState.remove_member(user.id), color_scheme="gray"),
        width="100%",
        align="center",
    )


def _members_dialog() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title(AdminState.group_label),
            rx.vstack(
                rx.foreach(AdminState.member_rows, _member),
                rx.hstack(
                    rx.select.root(
                        # flex + min_width 0 let the trigger shrink (Radix sets flex-shrink 0);
                        # its inner text truncates, so long addresses never push "Add" out.
                        rx.select.trigger(placeholder="Add a person…", flex="1", min_width="0"),
                        rx.select.content(
                            rx.foreach(
                                AdminState.member_candidates,
                                lambda u: rx.select.item(u.emails, value=u.id.to_string()),
                            )
                        ),
                        value=AdminState.member_pick,
                        on_change=AdminState.set_member_pick,
                    ),
                    rx.button("Add", on_click=AdminState.add_member, flex_shrink="0"),
                    width="100%",
                ),
                spacing="2",
                width="100%",
            ),
            rx.flex(
                rx.dialog.close(rx.button("Close", variant="soft", color_scheme="gray")),
                justify="end",
                margin_top="1em",
            ),
            max_width="30em",
        ),
        open=AdminState.members_open,
        on_open_change=AdminState.set_members_open,
    )


@rx.page(route=routes.ADMIN_GROUPS_ROUTE, title="Admin · Groups", on_load=AdminState.load_groups)
def admin_groups() -> rx.Component:
    return base_page(
        admin_page(
            "Groups",
            rx.button(rx.icon("plus", size=14), "New group", on_click=AdminState.new_group),
            rx.table.root(
                rx.table.header(
                    rx.table.row(
                        rx.table.column_header_cell("Name"),
                        rx.table.column_header_cell("Members"),
                        rx.table.column_header_cell(""),
                    )
                ),
                rx.table.body(rx.foreach(AdminState.groups, _row)),
                width="100%",
            ),
            _name_dialog(),
            _members_dialog(),
            confirm_dialog(
                open=AdminState.group_dialog == "delete",
                on_open_change=lambda _: AdminState.close_group_dialog(),
                on_confirm=AdminState.confirm_delete_group,
                title="Delete group?",
                description="Its members and shares go with it; what was shared stays.",
            ),
        )
    )
