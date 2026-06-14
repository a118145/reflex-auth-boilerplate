import reflex as rx

from ..ui import base_page

@rx.page(route="/login-req")
@base_page
def login_req_page() -> rx.Component:
    return rx.vstack(
        rx.heading(
            "Please login to view this page.", size="7",
            text_align="center",
            ),
        # rx.text(
        #     "API backend: ",
        #     rx.code(AppState.api_base_url),
        #     size="5",
        # ),
        spacing="5",
        align="center",
        justify="center",
        min_height="60vh",
        # width = '100vw', 
        
    )