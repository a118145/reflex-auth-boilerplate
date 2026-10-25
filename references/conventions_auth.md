# Auth conventions block for generated apps

Append everything below the line to the app's `AGENTS.md`, after the
conventions block from reflex-app-scaffold. Replace `{{app_name}}`. (Apps from
older scaffold versions still have `<!-- reflex managed -->` markers from
`reflex init`: append outside them, `reflex init` rewrites the inside.)

---

# Authentication and authorization

Magic-link sign-in for everyone on the allowed domains, a password login for
one admin, and secure-by-default authorization modelled on Reflex Enterprise.
Read `{{app_name}}/auth/__init__.py` for the module map.

## Folder contract additions

| Path | Holds |
| --- | --- |
| `auth/` | Everything auth: settings, tables, service, `/_auth` endpoints, middleware, policy, checks, mail transports. |
| `auth/state.py` | `AuthState` — the second state outside `states/` (like `NavState`). Written only by the middleware. |
| `auth/policy.py` | `PUBLIC_ROUTES`, `ROUTE_CHECKS`, `auth_event`. **The one place access is declared.** |
| `auth/authz.py` | Authorization checks, named for the question they answer. |
| `auth/housekeeping.py` | Daily lifespan task purging dead links, sessions and login attempts. |
| `auth/merge_hooks.py` | Re-points app tables when the admin merges two accounts. |
| `states/admin_state.py` | The admin area's state. Every handler is `auth=is_admin`. |

## Rules

1. **Everything requires a signed-in user unless `auth/policy.py` says
   otherwise.** New pages and new event handlers are protected without doing
   anything. Make something public only by adding it to `PUBLIC_ROUTES` or
   with `@auth_event(auth=False)` — and update `tests/test_auth_policy.py`,
   which pins the public surface.

2. **Authorization is declared, never written as `if` in a handler.** Use
   `@auth_event(auth=check)` for handlers and `ROUTE_CHECKS` for pages, with
   the check in `auth/authz.py`. A check that raises denies.

3. **Hiding is not enforcing.** `rx.cond(AuthState.is_admin, ...)` decides
   what to *show*; the check on the handler or route decides what is
   *allowed*. Every hidden control needs both.

4. **No secret ever goes into a public state var.** Tokens, keys, passwords
   and anything derived from them live in `_underscore` vars (backend only)
   or in environment variables read by the backend. Never read
   `self.router.headers.cookie` — the middleware removes the session cookie
   from the router data precisely because Reflex sends the router data to the
   browser.

5. **Load protected data only in protected handlers** (`on_load` included),
   and give state fields presentable defaults — that is what a signed-out
   visitor's browser holds. The middleware resets every app state when the
   signed-in user changes.

6. **Data that belongs to a person references `authuser.id`**, never an
   e-mail address (addresses change and can be merged). Add a hook to
   `auth/merge_hooks.py` for every such table.

7. **Sign-in and sign-out are HTTP, not events.** Only an HTTP response can
   set or clear the HttpOnly cookie, so the forms that do it are
   `components/native_form.py` posts to `/_auth/*`. `rx.form` and
   `rx.el.form` always `preventDefault` and cannot be used for that.

8. **Never add routes under `/_auth`**, and never add pages at `/login`,
   `/admin-login`, `/forbidden` or `/admin*` other than the generated ones.

9. **After adding a table**, run `uv run reflex db makemigrations` and
   commit the revision.

## Environment

All configuration is environment variables, documented in `.env.example`
and `auth/settings.py`. A bad value stops the app at startup rather than
weakening it. Generate the admin password hash with
`uv run python -m {{app_name}}.auth.hash_password`.
