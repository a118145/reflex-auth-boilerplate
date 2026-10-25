"""Landing page: brand, slogan, and the magic-link form. Public.

Signed-out visitors of any other page are sent here with ``redirect_to``.
The form only ever answers "check your inbox": whether a mail went out is
not revealed, so the page cannot be used to probe for accounts.
"""

import reflex as rx

from ..auth.state import AuthState
from ..components.auth_shell import auth_shell, brand
from ..navigation import routes


def _form() -> rx.Component:
    return rx.form(
        rx.vstack(
            rx.input(
                name="email",
                type="email",
                placeholder="you@company.com",
                custom_attrs={"autoComplete": "email"},
                required=True,
                size="3",
                width="100%",
            ),
            rx.el.input(type="hidden", name="redirect_to", value=AuthState.login_redirect_to),
            rx.cond(
                AuthState.form_error != "",
                rx.text(AuthState.form_error, color_scheme="red", size="2"),
            ),
            rx.button(
                rx.icon("mail", size=16), "Send sign-in link", type="submit", size="3", width="100%"
            ),
            spacing="3",
            width="100%",
        ),
        on_submit=AuthState.request_link,
        width="100%",
    )


def _sent() -> rx.Component:
    return rx.vstack(
        rx.icon("mail-check", size=36, color=rx.color("accent", 10)),
        rx.text(
            "If this address may sign in, a link is on its way. It works once and expires soon.",
            size="2",
            text_align="center",
        ),
        rx.button("Use another address", variant="ghost", on_click=AuthState.reset_login_form),
        spacing="3",
        align="center",
    )


@rx.page(route=routes.LOGIN_ROUTE, title="Sign in", on_load=AuthState.leave_public_page)
def login() -> rx.Component:
    return auth_shell(
        brand(),
        rx.cond(
            AuthState.login_error == "link",
            rx.callout(
                "That sign-in link has expired or was already used. Request a new one.",
                icon="triangle-alert",
                color_scheme="amber",
                size="1",
                width="100%",
            ),
        ),
        rx.cond(AuthState.link_sent, _sent(), _form()),
    )
