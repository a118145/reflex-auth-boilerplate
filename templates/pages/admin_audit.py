"""Admin: the latest security events. Route gated by ``authz.is_admin``."""

import reflex as rx

from ..auth.service import AuditRow
from ..components.admin import admin_page, muted
from ..navigation import routes
from ..states.admin_state import AdminState
from ..ui.base import base_page


def _row(row: AuditRow) -> rx.Component:
    return rx.table.row(
        rx.table.cell(muted(row.created_at)),
        rx.table.cell(rx.code(row.event, size="1")),
        rx.table.cell(rx.text(row.actor, size="2")),
        rx.table.cell(rx.text(row.subject, size="2")),
        rx.table.cell(muted(row.client_ip)),
        rx.table.cell(muted(row.detail)),
    )


@rx.page(route=routes.ADMIN_AUDIT_ROUTE, title="Admin · Audit log", on_load=AdminState.load_audit)
def admin_audit() -> rx.Component:
    return base_page(
        admin_page(
            "Audit log",
            rx.text(
                "The latest 200 events. Addresses without an account appear only as a hash.",
                size="2",
                color_scheme="gray",
            ),
            rx.table.root(
                rx.table.header(
                    rx.table.row(
                        rx.table.column_header_cell("When"),
                        rx.table.column_header_cell("Event"),
                        rx.table.column_header_cell("By"),
                        rx.table.column_header_cell("Account"),
                        rx.table.column_header_cell("IP"),
                        rx.table.column_header_cell("Detail"),
                    )
                ),
                rx.table.body(rx.foreach(AdminState.audit, _row)),
                width="100%",
                size="1",
            ),
        )
    )
