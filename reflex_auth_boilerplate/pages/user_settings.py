import reflex as rx
from ..navigation import routes
from ..ui import base_page
from ..states.auth_state import require_login
from ..states import SettingsState

@rx.page(
    route=routes.USER_SETTINGS_ROUTE,
    on_load=SettingsState.retrieve_user_info)
@base_page
@require_login
def user_settings_page() -> rx.Component:
    return rx.vstack(
        rx.heading("User Settings", size="9"),
        rx.text(
            f"User ID: {SettingsState.user_id} | Is admin: {SettingsState.is_admin}",
            # "Get started by editing ",
            # rx.code(f"{config.app_name}/{config.app_name}.py"),
            size="5",
        ),
        rx.link(
            rx.button("Check out our docs!"),
            href="https://reflex.dev/docs/getting-started/introduction/",
            is_external=True,
        ),
        spacing="5",
        justify="center",
        # min_height="55vh",
    )