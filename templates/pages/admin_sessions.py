"""Admin: live sessions — see and end them. Route gated by ``authz.is_admin``."""

import reflex as rx

from ..auth.service import SessionRow
from ..components.admin import admin_page, muted
from ..navigation import routes
from ..states.admin_state import AdminState
from ..ui.base import base_page


def _row(session: SessionRow) -> rx.Component:
    return rx.table.row(
        rx.table.row_header_cell(
            rx.hstack(
                rx.text(session.email),
                rx.cond(session.is_admin, rx.badge("Admin", variant="soft")),
                spacing="2",
            )
        ),
        rx.table.cell(muted(session.created_at)),
        rx.table.cell(muted(session.expires_at)),
        rx.table.cell(muted(session.client_ip)),
        rx.table.cell(
            rx.text(
                session.user_agent, size="1", color_scheme="gray", truncate=True, max_width="18em"
            )
        ),
        rx.table.cell(
            rx.button(
                "End",
                size="1",
                variant="soft",
                color_scheme="red",
                on_click=AdminState.revoke(session.id),
            )
        ),
    )


@rx.page(
    route=routes.ADMIN_SESSIONS_ROUTE, title="Admin · Sessions", on_load=AdminState.load_sessions
)
def admin_sessions() -> rx.Component:
    return base_page(
        admin_page(
            "Sessions",
            rx.text(
                "Ending a session signs that device out within a minute.",
                size="2",
                color_scheme="gray",
            ),
            rx.table.root(
                rx.table.header(
                    rx.table.row(
                        rx.table.column_header_cell("Signed in as"),
                        rx.table.column_header_cell("Since"),
                        rx.table.column_header_cell("Expires"),
                        rx.table.column_header_cell("IP"),
                        rx.table.column_header_cell("Browser"),
                        rx.table.column_header_cell(""),
                    )
                ),
                rx.table.body(rx.foreach(AdminState.sessions, _row)),
                width="100%",
            ),
        )
    )
