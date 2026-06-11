import reflex as rx

from ..ui import base_page

@rx.page(route="/404")
@base_page
def not_found_page() -> rx.Component:
    return rx.vstack(
        rx.heading("404", size="9"),
        rx.text("Page not found.", size="5"),
        # rx.link(
        #     "Back to home",
        #     href=routes.HOME_ROUTE,
        #     size="4",
        # ),
        spacing="4",
        align="center",
        justify="center",
        min_height="60vh",
    )


