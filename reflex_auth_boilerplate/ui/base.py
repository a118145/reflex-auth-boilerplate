import reflex as rx

from typing import Callable

from ..pages import browser_resize_page
from .nav import navbar
from .side import sidebar
from ..states import LoginState


def _page_shell(content: rx.Component) -> rx.Component:
    return rx.fragment(
        rx.desktop_only(
            rx.cond(
                LoginState.logged_in,
                sidebar(),
            ),
            # sidebar(),
            navbar(),
            content,
            height="100vh",
            overflow="hidden",
        ),
        rx.mobile_and_tablet(
            browser_resize_page(),
        ),
    )

def base_page(page: Callable[[], rx.Component]) -> rx.Component:
    return _page_shell(rx.container(page()))


def base_page_wide(page: Callable[[], rx.Component]) -> rx.Component:
    return _page_shell(
        rx.box(
            page(),
            max_width="1400px",
            width="100%",
            margin_x="auto",
            padding_x="16px",
            padding_y="16px",
        )
    )

