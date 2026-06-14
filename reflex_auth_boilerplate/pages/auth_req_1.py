import reflex as rx
from ..navigation import routes
from ..ui import base_page
from ..states.auth_state import require_login

@rx.page(route=routes.AUTH_REQUIRED_1_ROUTE)
@base_page
@require_login
def auth_req_1_page() -> rx.Component:
    return rx.center(
        rx.vstack(
            rx.heading("Auth required!", size="9"),
            rx.text(
                "Get started by editing ",
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
    )