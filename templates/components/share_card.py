"""The owner's "Share" card: visible to everyone, people by address, groups
by name (never members). Bound to ``ShareState``, which holds whatever is
open, whatever kind it is. The page shows the card to the owner only,
and the handlers' checks enforce it."""

from typing import Any

import reflex as rx

from ..states.share_state import ShareState


def _shared_row(label: rx.Var, title: str, on_click: Any) -> rx.Component:
    return rx.hstack(
        rx.text(label, size="2", flex="1"),
        rx.icon_button(
            rx.icon("x", size=14),
            variant="ghost",
            color_scheme="red",
            title=title,
            on_click=on_click,
        ),
        width="100%",
        align="center",
    )


def share_card(note: str) -> rx.Component:
    state = ShareState
    return rx.card(
        rx.vstack(
            rx.heading("Share", size="3"),
            rx.checkbox(
                "Visible to everyone",
                checked=state.shared_with_all,
                on_change=state.set_shared_with_all,
            ),
            rx.foreach(
                state.shares,
                lambda p: _shared_row(p["email"], "stop sharing", state.remove_share(p["id"])),
            ),
            rx.hstack(
                rx.input(
                    value=state.share_email,
                    on_change=state.set_share_email,
                    placeholder="name@company.com",
                    flex="1",
                ),
                rx.button("Share", on_click=state.add_share, variant="soft"),
                width="100%",
            ),
            rx.text("Groups", size="2", weight="medium"),
            rx.foreach(
                state.group_shares,
                lambda g: _shared_row(
                    g["name"], "stop sharing with this group", state.remove_group_share(g["id"])
                ),
            ),
            rx.hstack(
                rx.select.root(
                    rx.select.trigger(placeholder="Group…", flex="1"),
                    rx.select.content(
                        rx.foreach(
                            state.group_options, lambda g: rx.select.item(g["name"], value=g["id"])
                        )
                    ),
                    value=state.share_group,
                    on_change=state.set_share_group,
                ),
                rx.button("Share", on_click=state.add_group_share, variant="soft"),
                width="100%",
            ),
            rx.text(note, size="1", color_scheme="gray"),
            spacing="3",
            width="100%",
            align="start",
        ),
        width="100%",
    )
