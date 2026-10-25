"""Where a signed-in user lands on a page their account may not open. Public,
so it renders for anyone; it reveals nothing beyond "no access"."""

import reflex as rx

from ..components.auth_shell import auth_shell
from ..navigation import routes


@rx.page(route=routes.FORBIDDEN_ROUTE, title="No access")
def forbidden() -> rx.Component:
    return auth_shell(
        rx.icon("shield-x", size=40, color=rx.color("red", 10)),
        rx.heading("No access", size="6"),
        rx.text("Your account may not open that page.", color_scheme="gray", text_align="center"),
        rx.link(rx.button(rx.icon("house", size=16), "Back home"), href=routes.HOME_ROUTE),
    )
