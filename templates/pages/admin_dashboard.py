"""Admin: dashboard linking to the admin pages. Route gated by ``authz.is_admin``."""

import reflex as rx

from ..components.admin import admin_page
from ..navigation import routes
from ..states.admin_state import AdminState
from ..ui.base import base_page


def _card(label: str, icon: str, count: rx.Var[str], caption: str, href: str) -> rx.Component:
    return rx.link(
        rx.card(
            rx.hstack(
                rx.icon(icon, size=20, color=rx.color("accent", 10)),
                rx.vstack(
                    rx.text(label, weight="medium"),
                    rx.heading(count, size="5"),
                    rx.text(caption, size="1", color_scheme="gray"),
                    spacing="0",
                    align="start",
                ),
                spacing="3",
                align="center",
            ),
            width="100%",
        ),
        href=href,
        underline="none",
        color="inherit",
    )


@rx.page(route=routes.ADMIN_ROUTE, title="Admin", on_load=AdminState.load_dashboard)
def admin_dashboard() -> rx.Component:
    return base_page(
        admin_page(
            "Admin",
            rx.grid(
                _card(
                    "Users", "users", AdminState.user_count, "accounts", routes.ADMIN_USERS_ROUTE
                ),
                _card(
                    "Sessions",
                    "key-round",
                    AdminState.session_count,
                    "active now",
                    routes.ADMIN_SESSIONS_ROUTE,
                ),
                _card(
                    "Audit log",
                    "scroll-text",
                    AdminState.audit_week_count,
                    "entries, last 7 days",
                    routes.ADMIN_AUDIT_ROUTE,
                ),
                _card(
                    "Groups",
                    "users-round",
                    AdminState.group_count,
                    "groups",
                    routes.ADMIN_GROUPS_ROUTE,
                ),
                columns="4",
                spacing="3",
                width="100%",
            ),
        )
    )
