"""Admin: accounts — block, unblock, merge. Route gated by ``authz.is_admin``."""

import reflex as rx

from ..auth.service import UserRow
from ..components.admin import admin_page, muted
from ..components.confirm_dialog import confirm_dialog
from ..navigation import routes
from ..states.admin_state import AdminState
from ..ui.base import base_page


def _row(user: UserRow) -> rx.Component:
    return rx.table.row(
        rx.table.row_header_cell(
            rx.hstack(
                rx.text(user.emails),
                rx.cond(user.is_admin, rx.badge("Admin", variant="soft")),
                rx.cond(user.blocked, rx.badge("Blocked", color_scheme="red", variant="soft")),
                spacing="2",
                align="center",
            )
        ),
        rx.table.cell(muted(user.created_at)),
        rx.table.cell(muted(user.last_login_at)),
        rx.table.cell(user.active_sessions.to_string()),
        rx.table.cell(
            rx.cond(
                user.is_admin,
                rx.fragment(),
                rx.hstack(
                    rx.cond(
                        user.blocked,
                        rx.button(
                            "Unblock",
                            size="1",
                            variant="soft",
                            on_click=AdminState.ask_block(user.id, False),
                        ),
                        rx.button(
                            "Block",
                            size="1",
                            variant="soft",
                            color_scheme="red",
                            on_click=AdminState.ask_block(user.id, True),
                        ),
                    ),
                    rx.button(
                        rx.icon("merge", size=14),
                        "Merge…",
                        size="1",
                        variant="soft",
                        color_scheme="gray",
                        disabled=user.blocked,
                        on_click=AdminState.open_merge(user.id),
                    ),
                    spacing="3",
                ),
            )
        ),
    )


def _merge_dialog() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title("Merge accounts"),
            rx.dialog.description(
                rx.text(
                    "The addresses of ",
                    rx.text.strong(AdminState.merge_source_label),
                    " move to the account you pick. That account keeps its data; the other one is "
                    "deleted. Both are signed out everywhere.",
                ),
            ),
            rx.select.root(
                rx.select.trigger(placeholder="Merge into…", width="100%"),
                rx.select.content(
                    rx.foreach(
                        AdminState.merge_candidates,
                        lambda u: rx.select.item(u.emails, value=u.id.to_string()),
                    )
                ),
                value=AdminState.merge_target_id,
                on_change=AdminState.set_merge_target,
            ),
            rx.flex(
                rx.dialog.close(rx.button("Cancel", variant="soft", color_scheme="gray")),
                rx.button("Merge", color_scheme="red", on_click=AdminState.confirm_merge),
                spacing="3",
                justify="end",
                margin_top="1em",
            ),
            max_width="30em",
        ),
        open=AdminState.merge_open,
        on_open_change=AdminState.set_merge_open,
    )


@rx.page(route=routes.ADMIN_ROUTE, title="Admin · Users", on_load=AdminState.load_users)
def admin_users() -> rx.Component:
    return base_page(
        admin_page(
            "Users",
            rx.table.root(
                rx.table.header(
                    rx.table.row(
                        rx.table.column_header_cell("Addresses"),
                        rx.table.column_header_cell("Created"),
                        rx.table.column_header_cell("Last sign-in"),
                        rx.table.column_header_cell("Sessions"),
                        rx.table.column_header_cell(""),
                    )
                ),
                rx.table.body(rx.foreach(AdminState.users, _row)),
                width="100%",
            ),
            _merge_dialog(),
            confirm_dialog(
                open=AdminState.block_open,
                on_open_change=AdminState.set_block_open,
                on_confirm=AdminState.confirm_block,
                title=rx.cond(
                    AdminState.block_target_blocked, "Block account?", "Unblock account?"
                ),
                description=rx.cond(
                    AdminState.block_target_blocked,
                    "All its sessions end now and it cannot request sign-in links.",
                    "The account can sign in again.",
                ),
                confirm_label=rx.cond(AdminState.block_target_blocked, "Block", "Unblock"),
            ),
        )
    )
