
import reflex as rx

from ..states import AuthState
from ..navigation.nav_config import NAV_ITEMS
from ..navigation.state import NavState
from ..navigation import routes

def navbar_link(text: str, url: str) -> rx.Component:
    return rx.link(rx.text(text, size="4", weight="medium"), href=url)


def navbar_item(text: str, icon: str, index: int) -> rx.Component:
    return rx.button(
        rx.icon(icon, size=18),
        rx.text(text, size="4", weight="medium"),
        # padding_x="0.75rem",
        # padding_y="0.5rem",
        align="center",
        cursor="pointer",
        size="3",
        # disabled=~LoginState.logged_in,
        on_click=NavState.set_active(index),
        bg=rx.cond(
            NavState.symbol_active[index],
            rx.color("accent", 5),
            "transparent",
        ),
        color=rx.cond(
            NavState.symbol_active[index],
            rx.color("accent", 11),
            "inherit",
        ),
        # style=rx.cond(
        #     LoginState.logged_in,
        #     {
        #         "_hover": {
        #             "bg": rx.color("accent", 4),
        #             "color": rx.color("accent", 11),
        #         },
        #         "border-radius": "0.5em",
        #     },
        #     {}
        # ),
        style={
            "_hover": {
                "bg": rx.color("accent", 4),
                "color": rx.color("accent", 11),
            },
            "border-radius": "0.5em",
        }
    )

def navbar_item_new(text: str, icon: str, index: int) -> rx.Component:
    return rx.icon_button(
        rx.icon(icon, size=18),
        rx.text(text, size="4", weight="medium"),
        # padding_x="0.75rem",
        # padding_y="0.5rem",
        # align="center",
        # cursor="pointer",
        on_click=NavState.set_active(index),
        bg=rx.cond(
            NavState.symbol_active[index],
            rx.color("accent", 5),
            "transparent",
        ),
        color=rx.cond(
            NavState.symbol_active[index],
            rx.color("accent", 11),
            "inherit",
        ),
        style={
            "_hover": {
                "bg": rx.color("accent", 4),
                "color": rx.color("accent", 11),
            },
            "border-radius": "0.5em",
        },
    )

def navbar() -> rx.Component:
    nav_links = [
        navbar_item(item["label"], item["icon"], i)
        for i, item in enumerate(NAV_ITEMS)
    ]
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
                *nav_links,
                justify="center",
                spacing="5",
                # flex="1",
            ),
            rx.hstack(
                rx.cond(
                    AuthState.is_logged_in,
                    rx.menu.root(
                        rx.menu.trigger(
                            rx.icon_button(
                                rx.icon("user"), 
                                size="3", 
                                radius="full",
                            ),
                        ),
                        rx.menu.content(
                            rx.menu.item(
                                "Settings",
                                on_click=NavState.to_settings,
                            ),
                            rx.menu.item(
                                "Logout", 
                                on_click=AuthState.open_dialog('logout'),
                            ),
                        ),
                    ),
                    # rx.hstack(
                    #     rx.icon_button(
                    #         rx.icon("user"), size="3", radius="full"
                    #     ),
                    #     rx.vstack(
                    #         rx.box(
                    #             rx.text("My account", size="3", weight="bold"),
                    #             rx.text(
                    #                 "user@reflex.dev", size="2", weight="medium"
                    #             ),
                    #             width="100%",
                    #         ),
                    #         spacing="0",
                    #         align="start",
                    #         justify="start",
                    #         width="100%",
                    #     ),
                    #     rx.icon_button(rx.icon("log-out"), size="3", radius="full", on_click=AuthState.open_dialog("logout")),
                    #     padding_x="0.5rem",
                    #     align="center",
                    #     justify="start",
                    #     width="100%",
                    # ),
                    rx.menu.root(
                        rx.menu.trigger(
                            rx.icon_button(rx.icon("log-in"), size="3", radius="full"),
                        ),
                        rx.menu.content(
                            rx.menu.item(
                                "Login",
                                on_click=AuthState.open_dialog('login'),
                            ),
                            rx.menu.item(
                                "Register", 
                                on_click=AuthState.open_dialog('register'),
                            ),
                        ),
                    )
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
        top="0px",
        z_index="5",
        width="100%",
    )