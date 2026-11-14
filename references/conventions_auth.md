# Auth conventions block for generated apps

Append everything below the line to the app's `AGENTS.md`, after the
conventions block from reflex-app-scaffold. Replace `{{app_name}}`. (Apps from
older scaffold versions still have `<!-- reflex managed -->` markers from
`reflex init`: append outside them, `reflex init` rewrites the inside.)

---

# Authentication, authorization and multi-user data

Magic-link sign-in for everyone on the allowed domains, a password login for
one admin, secure-by-default authorization, and a service layer that
enforces ownership and sharing. Read `{{app_name}}/auth/__init__.py` and
`{{app_name}}/service/__init__.py` for the module maps.

## Folder contract additions

| Path | Holds |
| --- | --- |
| `auth/` | Everything auth: settings, tables, service, `/_auth` endpoints, middleware, policy, checks, mail transports. |
| `auth/state.py` | `AuthState` — the second state outside `states/` (like `NavState`). Written only by the middleware. |
| `auth/policy.py` | `PUBLIC_ROUTES`, `ROUTE_CHECKS`, `auth_event` and the named decorators. **The one place access is declared.** |
| `auth/authz.py` | Authorization checks, named for the question they answer. |
| `auth/upload_gate.py` | Checks the session cookie on `POST /_upload` and grants the upload's event. |
| `auth/directory.py` | People by id and by address, for display (`emails_for`, `user_by_email`). |
| `auth/housekeeping.py` | Daily lifespan task purging dead links, sessions and login attempts. |
| `auth/merge_hooks.py` | Hands merge and delete of accounts to `service/people.py`. |
| `service/` | **The rules.** Use cases that take the acting user's id and check what that user may see or do. One module per area; `views` holds what each screen shows, made of the plain values in `wire` (never a table row); `sharing` is used by its own name; `__init__` re-exports everything else. Never imports `reflex` or the UI. |
| `service/models.py` | The service's own tables (groups) and which columns hold a person (`OWNER_COLUMNS`, `GRANTEE_COLUMNS`). |
| `utils/db.py` | `call` / `in_session` — the only place the app opens a database session. |
| `states/handlers.py` | `toast_errors`, and `call` re-exported: what every handler that reaches the service has in common. |
| `states/people.py` | `actor_id` — who is acting, from the gate. |
| `states/share_state.py`, `components/share_card.py` | Sharing, for every shareable kind. |
| `states/admin_state.py` | The admin area's state. Every handler is `admin_event`. |

## Rules

1. **Everything requires a signed-in user unless `auth/policy.py` says
   otherwise.** New pages and new event handlers are protected without doing
   anything — a page needs no `on_load` for that: the first load and every
   navigation are gated. Make something public only by adding it to `PUBLIC_ROUTES` or
   with `@auth_event(auth=False)` — and update `tests/test_auth_policy.py`,
   which pins the public surface.

2. **Authorization is declared, never written as `if` in a handler.** Use
   the named decorators in `auth/policy.py` (`admin_event`,
   `share_owner_event`, …) for handlers and `ROUTE_CHECKS` for pages, with
   the check in `auth/authz.py`. A new check gets a new named decorator
   there; states never spell out `auth_event(auth=...)`. A check that raises
   denies. `tests/test_auth_policy.py` lists, per state, which handlers are
   left to any signed-in user.

3. **Hiding is not enforcing.** `rx.cond(AuthState.is_admin, ...)` or
   `rx.cond(row.mine, ...)` decides what to *show*; the check on the handler
   and the service decide what is *allowed*. Every hidden control needs
   both.

4. **The service is the gate.** A handler hands a use case from `service/`
   to `call` (`states/handlers.py`), with `await actor_id(self)` as the
   acting user. The use case checks; a declared check on the handler is only
   a pre-filter. No `rx.session`, `select`, `db.get` or table import in
   states, components, pages or utils — `tests/test_architecture.py` checks
   (its `LEGACY` list may only shrink). What a screen shows comes from one
   use case as plain values from `service/wire.py`. "Missing" and "not
   yours" give the same refusal.

5. **Handlers let refusals rise.** A handler that calls the service carries
   `@toast_errors` directly under its event decorator; the service's
   `PermissionDeniedError` / `DomainError` then becomes the error toast. Ids
   from the browser go through `utils/casting.as_id`, never a bare
   `int(...)`. Catch a refusal in a handler only to restore or show
   something first, and say what on the first line of the `except` block.
   `tests/test_handlers.py` checks all three.

6. **Data that belongs to a person references `authuser.id`** with a foreign
   key, never an e-mail address (addresses change and accounts are merged).
   A thing has exactly one owner. Declare the column in `OWNER_COLUMNS` /
   `GRANTEE_COLUMNS` (`service/models.py`) or make the table a `Shareable`;
   `tests/test_people.py` fails for a person column that merge and delete
   would miss.

7. **Sharing is implemented once**, in `service/sharing.py`. A new shareable
   kind is two share tables, one `Shareable(...)` in `KINDS` and one
   `load_*` handler in `states/share_state.py` — never a copy of the
   functions. Lists use `sharing.readable`, single reads
   `sharing.get_viewable`, writes start with `sharing.owned`. There is no
   admin bypass.

8. **No secret ever goes into a public state var.** Tokens, keys, passwords
   and anything derived from them live in `_underscore` vars (backend only)
   or in environment variables read by the backend. Never read
   `self.router.headers.cookie` — on the backend it holds the full cookie
   string, so the middleware removes the session cookie from every event's
   router data. The Reflex client token is **not** a credential (it is in
   `sessionStorage` and in the socket URL): only an event that arrived on a
   socket, with that socket's handshake cookie, signs anyone in. Never trust
   a key in `router_data` — the browser can add any.
   `tests/test_auth_event_origin.py` guards this against the real event
   processor.

9. **Load protected data only in protected handlers** (`on_load` included),
   and give state fields presentable defaults — that is what a signed-out
   visitor's browser holds. The middleware resets every app state when the
   signed-in user changes.

10. **Sign-in and sign-out are HTTP, not events.** Only an HTTP response can
    set or clear the HttpOnly cookie, so the forms that do it are
    `components/native_form.py` posts to `/_auth/*`. `rx.form` and
    `rx.el.form` always `preventDefault` and cannot be used for that.

11. **Upload handlers do not return or yield backend events.** An upload is
    an HTTP request; its event runs under a grant from `auth/upload_gate.py`
    that covers that one event. Trigger follow-up work from the page
    instead.

12. **Never add routes under `/_auth`**, and never add pages at `/login`,
    `/admin-login`, `/forbidden` or `/admin*` other than the generated ones.
    Every `/admin*` page is listed in `ROUTE_CHECKS`.

13. **Reflex stays pinned** (`reflex[db]==0.11.0`). The gate rests on
    private Reflex behaviour; an upgrade is its own change, verified with
    `tests/test_auth_event_origin.py` and a look at the WebSocket frames.

14. **After adding a table**, run `uv run reflex db makemigrations` and
    commit the revision. A foreign key added to an existing table needs a
    name in the revision (SQLite).

## Environment

All configuration is environment variables, documented in `.env.example`
and `auth/settings.py`. A bad value stops the app at startup rather than
weakening it; in production `REFLEX_API_URL` and `REFLEX_DEPLOY_URL` must be
the same `https://` origin. Generate the admin password hash with
`uv run python -m {{app_name}}.auth.hash_password`.
