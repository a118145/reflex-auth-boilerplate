import reflex as rx

from ..states import AuthState
from .dialog_general import dialog_buttons


def logout_dialog() -> rx.Component:
    """Logout dialog for logging out users."""
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title(
                "Are you sure to log out?"
            ),
            dialog_buttons("logout"),
            spacing="3",
            width="100%",
        
            
            max_width="300px",
        ),
        open=AuthState.logout_dialog_open,
    )