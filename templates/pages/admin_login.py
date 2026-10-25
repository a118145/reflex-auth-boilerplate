"""Admin password login. Public, and deliberately not linked from anywhere.

The form is a plain HTML ``POST`` to the backend (``/_auth/admin-login``,
via ``native_form``), not a Reflex form: the password goes straight to the endpoint and never
passes through a Reflex state, and only an HTTP response can set the
HttpOnly session cookie.
"""

import reflex as rx

from ..auth.state import AuthState, backend_url
from ..components.auth_shell import auth_shell, brand
from ..components.native_form import native_form
from ..navigation import routes

_ERRORS = {
    "invalid": "Wrong e-mail address or password.",
    "locked": "Too many failed attempts. Try again later.",
    "disabled": "Admin login is not configured on this server.",
}


def _error() -> rx.Component:
    return rx.match(
        AuthState.login_error,
        *[
            (
                code,
                rx.callout(text, icon="triangle-alert", color_scheme="red", size="1", width="100%"),
            )
            for code, text in _ERRORS.items()
        ],
        rx.fragment(),
    )


@rx.page(route=routes.ADMIN_LOGIN_ROUTE, title="Admin sign in", on_load=AuthState.leave_public_page)
def admin_login() -> rx.Component:
    return auth_shell(
        brand(),
        rx.heading("Admin", size="4"),
        _error(),
        native_form(
            rx.vstack(
                rx.input(
                    name="email",
                    type="email",
                    placeholder="E-mail",
                    custom_attrs={"autoComplete": "username"},
                    required=True,
                    size="3",
                    width="100%",
                ),
                rx.input(
                    name="password",
                    type="password",
                    placeholder="Password",
                    custom_attrs={"autoComplete": "current-password"},
                    required=True,
                    size="3",
                    width="100%",
                ),
                rx.el.input(type="hidden", name="redirect_to", value=AuthState.login_redirect_to),
                rx.button("Sign in", type="submit", size="3", width="100%"),
                spacing="3",
                width="100%",
            ),
            method="post",
            action=backend_url("/admin-login"),
            width="100%",
        ),
    )
