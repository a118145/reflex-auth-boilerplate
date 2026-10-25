"""Signed-in user and logout, at the end of the navigation.

Logout is a plain HTML ``POST`` to the backend (``native_form``), not a Reflex event: only an
HTTP response can clear the HttpOnly session cookie. ``SameSite=Lax`` plus the
endpoint's origin check make it CSRF-safe.

``admin_only`` hides admin menu entries from everyone else. That is
presentation only — the admin routes and handlers are enforced by
``auth/policy.py`` whatever the menu shows.
"""

import reflex as rx

from ..auth.state import AuthState, backend_url
from ..components.native_form import native_form
from ..navigation.nav_config import NavItem


def admin_only(item: NavItem, component: rx.Component) -> rx.Component:
    """Render ``component`` only for the admin if ``item`` is ``admin_only``."""
    if item.get("admin_only"):
        return rx.cond(AuthState.is_admin, component, rx.fragment())
    return component


def _logout_form(button: rx.Component, *, everywhere: bool) -> rx.Component:
    return native_form(
        rx.el.input(type="hidden", name="everywhere", value="1" if everywhere else "0"),
        button,
        method="post",
        action=backend_url("/logout"),
    )


def _who() -> rx.Component:
    return rx.hstack(
        rx.icon("circle-user-round", size=18, color=rx.color("accent", 10)),
        rx.text(AuthState.user_email, size="2", weight="medium", trim="both", truncate=True),
        rx.cond(AuthState.is_admin, rx.badge("Admin", size="1", variant="soft")),
        align="center",
        spacing="2",
        min_width="0",
    )


def account_block_vertical() -> rx.Component:
    """For the bottom of a sidebar."""
    return rx.vstack(
        rx.separator(size="4"),
        _who(),
        rx.hstack(
            _logout_form(
                rx.button(
                    rx.icon("log-out", size=14), "Log out", type="submit", size="1", variant="soft"
                ),
                everywhere=False,
            ),
            _logout_form(
                rx.button(
                    "All devices",
                    type="submit",
                    size="1",
                    variant="soft",
                    color_scheme="gray",
                    title="Log out on every device",
                ),
                everywhere=True,
            ),
            spacing="2",
            align="center",
        ),
        spacing="2",
        width="100%",
        padding_x="0.6rem",
    )


def account_block_inline() -> rx.Component:
    """For the right end of a top bar."""
    return rx.hstack(
        _who(),
        _logout_form(
            rx.tooltip(
                rx.icon_button(rx.icon("log-out", size=18), type="submit", variant="ghost"),
                content="Log out",
            ),
            everywhere=False,
        ),
        _logout_form(
            rx.tooltip(
                rx.icon_button(
                    rx.icon("monitor-off", size=18),
                    type="submit",
                    variant="ghost",
                    color_scheme="gray",
                ),
                content="Log out on every device",
            ),
            everywhere=True,
        ),
        spacing="3",
        align="center",
    )
