
import reflex as rx

from ..states import LoginState

def navbar_link(text: str, url: str) -> rx.Component:
    return rx.link(rx.text(text, size="4", weight="medium"), href=url)


def navbar() -> rx.Component:
    return rx.box(
        rx.hstack(
            rx.hstack(
                rx.image(
                    src="https://web.reflex-assets.dev/other/logo.jpg",
                    width="2.25em",
                    height="auto",
                    border_radius="25%",
                ),
                rx.heading("Reflex", size="7", weight="bold"),
                align_items="center",
            ),
            rx.hstack(
                navbar_link("Home", "/#"),
                navbar_link("About", "/#"),
                navbar_link("Pricing", "/#"),
                navbar_link("Contact", "/#"),
                spacing="5",
            ),
            rx.hstack(
                rx.cond(
                    LoginState.logged_in,
                    rx.button("Log Out", size="3", on_click=LoginState.logout),
                    rx.fragment(
                        rx.button("Sign Up", size="3", variant="outline"),
                        rx.button("Log In", size="3", on_click=LoginState.login),
                    ),
                ),
                spacing="4",
                justify="end",
            ),
            justify="between",
            align_items="center",
        ),
        bg=rx.color("accent", 3),
        padding="1em",
        # position="fixed",
        # top="0px",
        # z_index="5",
        width="100%",
    )