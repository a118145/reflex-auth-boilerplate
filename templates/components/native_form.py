"""A ``<form>`` the browser submits itself, as a real HTTP POST.

``rx.form`` and ``rx.el.form`` both always attach an ``onSubmit`` handler
that calls ``preventDefault`` (``Form.create`` installs one when no
``on_submit`` is given), so a form built with them can never reach a backend
URL. The auth endpoints need exactly that: only an HTTP response can set or
clear the HttpOnly session cookie, and the admin password should go straight
to the endpoint without passing through a Reflex state.
"""

from typing import ClassVar

import reflex as rx


class NativeForm(rx.Component):
    tag = "form"
    # Render the tag as the HTML element "form", not as a JS identifier
    # `form` (which fails the production build with "form is not defined").
    # This is how Reflex's own raw elements (`rx.el.*`) do it.
    _is_tag_in_global_scope: ClassVar[bool] = True

    action: rx.Var[str]
    method: rx.Var[str]


native_form = NativeForm.create
