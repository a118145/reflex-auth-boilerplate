"""Magic-link authentication and route/event authorization.

Deliberately free of re-exports: ``state`` imports ``service``, ``middleware``
imports ``state`` and ``policy``, and pages import all of them. Import from the
module that defines a name, e.g. ``from ..auth.policy import auth_event``.

Module map:

* ``settings``   — environment configuration, validated once at import
* ``models``     — SQLModel tables (users, emails, link tokens, sessions, audit)
* ``security``   — token/password hashing, redirect validation, client IP
* ``service``    — every database operation; plain functions over a Session
* ``endpoints``  — backend HTTP routes that set and clear the session cookie
* ``middleware`` — strips the cookie from router data and gates every event
* ``policy``     — public routes, route checks, ``auth_event``
* ``authz``      — the authorization checks themselves
* ``state``      — ``AuthState``: who is signed in, for rendering only
* ``mail/``      — magic-link delivery (console, SMTP, Mailgun, Microsoft Graph)
"""
