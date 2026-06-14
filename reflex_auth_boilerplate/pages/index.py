import reflex as rx
from ..navigation import routes
from ..ui import base_page

@rx.page(route=routes.HOME_ROUTE)
@base_page
def index() -> rx.Component:
    # Welcome Page (Index)
    return rx.center(
        rx.vstack(
            rx.heading("Welcome to Reflex!", size="9"),
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