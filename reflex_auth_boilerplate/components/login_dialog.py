import reflex as rx

from ..states import AuthState
from .dialog_general import dialog_buttons, LOGIN_FIELDS, render_dialog_field


def login_dialog() -> rx.Component:
    """Login dialog for authenticating users."""
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title(
                "Login"
            ),
            rx.form(
                rx.vstack(
                    rx.foreach(
                        LOGIN_FIELDS,
                        lambda field: render_dialog_field(field),
                    ),
                    rx.cond(
                        AuthState.dialog_error != "",
                        rx.callout(
                            AuthState.dialog_error,
                            icon="triangle-alert",
                            color_scheme="red",
                            size="1",
                            width="100%",
                        ),
                    ),
                    dialog_buttons('login'),
                    spacing="3",
                    width="100%",
                ),
                on_submit=AuthState.login,
                reset_on_submit=False,
            ),
            max_width="300px",
        ),
        open=AuthState.login_dialog_open,
    )