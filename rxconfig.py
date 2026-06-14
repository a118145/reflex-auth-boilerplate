import reflex as rx

config = rx.Config(
    app_name="reflex_auth_boilerplate",
    plugins=[
        rx.plugins.SitemapPlugin(),
        rx.plugins.TailwindV4Plugin(),
    ],
    db_url="sqlite:///reflex_auth_boilerplate.db",
)
