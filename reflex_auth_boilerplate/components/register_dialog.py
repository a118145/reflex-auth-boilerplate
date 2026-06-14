import reflex as rx

from ..states import AuthState
from .dialog_general import dialog_buttons, REGISTER_FIELDS, render_dialog_field


def register_dialog() -> rx.Component:
    """Register dialog for creating new users."""
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title(
                "Register"
            ),
            rx.form(
                rx.vstack(
                    rx.foreach(
                        REGISTER_FIELDS,
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
                    dialog_buttons('register'),
                    spacing="3",
                    width="100%",
                ),
                on_submit=AuthState.register,
                reset_on_submit=False,
            ),
            max_width="300px",
        ),
        open=AuthState.register_dialog_open,
    )