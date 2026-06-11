import reflex as rx

def browser_resize_page() -> rx.Component:
    return rx.vstack(
        rx.heading(
            "Please resize your browser window to view the content.", size="7",
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
        min_height="85vh",
        width = '100vw', 
        
    )