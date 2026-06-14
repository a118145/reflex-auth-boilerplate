import reflex as rx
from reflex_auth_boilerplate.ui import base
from ..navigation import routes
from ..ui import base_page
from ..components import changelog_card

@rx.page(route=routes.ABOUT_ROUTE)
@base_page
def about_page() -> rx.Component:
    return rx.vstack(
        rx.heading("Version history", size="7"),
        changelog_card(
            version="0.1.0",
            date="2025-10-15",
            description=[
                "Initial release",
            ],
        ),
        rx.heading("License", size="7"),
        rx.card(
            rx.markdown(
                """Copyright 2026 Arne Claus Feldkamp

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE."""
            ),
            variant="classic",
        ),
    )
