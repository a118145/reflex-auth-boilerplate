import reflex as rx

def changelog_card(version: str, date: str, description: list[str]) -> rx.Component:
    return rx.card(
        rx.inset(
            rx.hstack(
                rx.heading(f"v{version}", size="5"),
                rx.badge(f"released on {date}", size="1"),
                justify="between",
                align="center",
                padding_x="0.5rem",
            ),
            rx.separator(),
            side="top",
        ),
        rx.vstack(
            rx.list.unordered(
                *[rx.list.item(desc) for desc in description],
                spacing="2",
            ),
        ),
        padding="4",
        width="100%",
        variant="classic",
        size="2",
    )