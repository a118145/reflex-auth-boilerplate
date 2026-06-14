from turtle import width
import reflex as rx

from ..states import AuthState

def dialog_buttons(dialog_type: str) -> rx.Component:
    """Dialog buttons for opening and closing dialogs."""
    return rx.hstack(
        rx.dialog.close(
            rx.button(
                "Cancel",
                variant="soft",
                color_scheme="gray",
                type='button',
                on_click=lambda: AuthState.close_dialog(dialog_type),
            ),
        ),
        rx.match(
            dialog_type,
            ("login", 
                rx.button(
                    "Login",
                    variant="solid",
                    color_scheme="green",
                    # on_click=lambda: AuthState.login(),
                    type="submit",
                )
            ),
            ("register",
                rx.button(
                    "Register",
                    variant="solid",
                    color_scheme="green",
                    # on_click=lambda: AuthState.register(),
                    type="submit",
                )
            ),
            ("logout",
                rx.button(
                    "Logout",
                    variant="solid",
                    color_scheme="green",
                    on_click=lambda: AuthState.logout(),
                    type="button",
                )
            ),
        ),
        spacing="3",
        justify="end",
        width="100%",
    )

LOGIN_FIELDS: list[dict[str, str]] = [
    # {"name": "username", "label": "Username", "type": "text"},
    {"name": "mail", "label": "Email", "type": "email"},
    {"name": "password", "label": "Password", "type": "password"},
]

REGISTER_FIELDS: list[dict[str, str]] = [
    {"name": "mail", "label": "Email", "type": "email"},
    {"name": "password", "label": "Password", "type": "password"},
    {"name": "confirm_password", "label": "Confirm Password", "type": "password"},
]

def render_dialog_field(field: dict[str, str]) -> rx.Component:
    """Render a dialog field based on the field name and data."""
    return rx.input(
        placeholder=field["label"],
        type=field["type"],
        name=field["name"],
        width="100%",
    )