# Reflex 0.10.1 — facts this skill depends on

Each one verified against the installed package source and, where marked,
against the real event processor or in a running app. Several are private
behaviour: **the skill pins `reflex==0.10.1`**, and after any upgrade
`tests/test_auth_event_origin.py`, `test_auth_middleware.py` and the browser
check "no WebSocket frame contains the token" must be run again before
trusting the result.

## Reflex 0.11 is not supported yet

A fresh `uv add reflex` installs 0.11.0 (November 2026). Applying the
templates there showed, before any deeper verification:

| Change in 0.11.0 | Effect |
| --- | --- |
| `rx.event(fn)` returns a frozen object | `auth_event` cannot set its policy attribute on the handler: every state fails to import (`FrozenInstanceError`). |
| `deploy_url` defaults to `None` (was `http://localhost:3000`) | `auth/origin.py` no longer accepts the dev frontend's origin; links and `form-action` built from `deploy_url` are empty in development. |
| Reflex applies its own origin and CORS rules derived from `deploy_url` | The assumptions behind `rxconfig._own_origins` and the upload gate must be re-verified. |

Do not paper over these one by one. Supporting 0.11 means re-verifying every
section below and updating this file; until then pin 0.10.1 (SKILL.md
Step 1).

## Where an event comes from

Verified by `tests/test_auth_event_origin.py`, which drives
`app.event_processor`; `auth/middleware.py:event_origin` depends on it.

| Origin | `event.router_data` | `EventContext.get()` in a middleware |
| --- | --- | --- |
| Browser, over the socket (`EventNamespace.on_event`) | The browser's dict, with `headers`, `sid`, `ip`, `query` and `token` **overwritten** by the server from the connection. Any other key the browser sent is still in it. | Same dict object as `event.router_data`; `parent_txid is None`. |
| Queued by a handler (returned/yielded events, a page's `on_load` handlers) | `{}` | `router_data` inherited from the event that started the chain; `parent_txid` set. |
| `POST /_upload` | `{}` | Forked from the processor's root context: `router_data == {}`, `parent_txid is None`. |

- The headers in a socket event are a fresh copy of the handshake's on every
  event, cookie included. Mutating them does not carry over to the next
  event.
- The client token is the `Reflex-Client-Token` request header on uploads
  and `?token=` on the socket URL; the browser keeps it in `sessionStorage`.
  It is not a secret.
- The upload request is an `XMLHttpRequest` without `withCredentials`: it
  carries cookies only when page and backend share an origin.
- `EventContext` is imported from `reflex_base.event.context`.
- `App._setup_event_processor()` (async context manager) plus
  `app.set_contexts()` is enough to run events through the real processor in
  a test, without a server.

## Router data and the browser

`State.router` is a descriptor over five per-field state vars
(`rx_router_session`, `rx_router_headers`, `rx_router_page`,
`rx_router_url`, `rx_router_route_id`); a navigation re-sends only the
URL/page vars.

Since 0.10.0 the headers serialised to the browser omit `cookie`, and
`raw_headers` drops `cookie`, `authorization`, `proxy-authorization` and
common proxy/IAP token headers. (Up to 0.9.8 the cookie *was* sent: an
HttpOnly cookie's value appeared in the WebSocket frames.) On the backend,
`self.router.headers.cookie` and `raw_headers["cookie"]` still hold the full
cookie string — which is why the middleware strips the session cookie from
every socket event's router data. Every other handshake header still reaches
the browser: never put a secret in one.

`router.session.client_ip` ignores `X-Forwarded-For` unless
`rx.Config(trusted_proxy_hops=N)` is set (default 0). The socket peer is in
`router_data["headers"]["asgi-scope-client"]`; the auth code uses that plus
its own `AUTH_TRUSTED_PROXIES`.

## Event middleware

`reflex.middleware.middleware.Middleware` (import from that module) with
`async preprocess(app, state, event) -> StateUpdate | None`.
`app.add_middleware(mw, index=0)`. Called with the **root state**, after
`state.router_data`/`state.router` were set from the event and **before**
the handler runs or any delta is computed. Returning a `StateUpdate` skips
the handler; its `events` are sent
(`Event.from_event_type(rx.redirect(...))`). Applies to hydrate,
`on_load_internal`, user handlers and upload handlers.

Page loads arrive as `<OnLoadInternalState full name>.on_load_internal`;
`state.router.route_id` is the matched route pattern (e.g.
`/data/[item_id]`, `/404` for unknown paths).

## HTTP routes next to the app

`rx.App(api_transformer=Starlette(...))`: Reflex adds CORS and mounts itself
below at `""`, so these routes win, and **middleware on that Starlette sees
Reflex's own routes** (`/_upload`, `/_event`) — that is how the upload gate
works. Same path with different methods works. In dev the backend is
`api_url` (`:8000`) and the frontend dev server (`:3000`) does **not** proxy
backend paths — links and form actions must use `api_url`. Cookies are not
port-bound, so a cookie set by `localhost:8000` is sent to the
`localhost:3000` page and its WebSocket to `:8000` (same site) — but not
with the upload XHR (cross-origin, no credentials).

`cors_allowed_origins` defaults to `*`; `rxconfig.py` sets it to the origins
of `REFLEX_DEPLOY_URL` and `REFLEX_API_URL`.

`--single-port` requires `--env prod`; set `REFLEX_DEPLOY_URL` and
`REFLEX_API_URL` to the same public URL. The prod static server redirects
`/data` → `/data/` (307).

`reflex run --env prod` serves with Granian when `uvicorn`/`gunicorn` are not
installed. Reflex does not pass `log_access` and Granian's default is off:
the app writes **no access log**, so query strings (`/_auth/link?t=…`,
`/_event?token=…`) do not reach it. A reverse proxy in front usually does
log them — see `deployment.md`.

## Forms

`rx.form` **and** `rx.el.form` always attach an `onSubmit` that calls
`preventDefault` — a native POST to a backend URL is impossible with them.
`components/native_form.py` is a bare `rx.Component` with `tag = "form"` and
`_is_tag_in_global_scope = True` (without that flag the production build
fails with `ReferenceError: form is not defined`, while dev mode hides it).

`rx.input(auto_complete=...)` takes the HTML string (`"email"`,
`"current-password"`) since 0.10; `custom_attrs={"autoComplete": ...}` still
works.

## State

- `State.reset()` resets base and backend vars (not `router`) and recurses
  into **loaded** substates only; to reset everything, `get_state` each
  class (`cls.get_substates()` recursively).
- `State(**{"_reflex_internal_init": True})` builds a root state in tests.
- `EventHandler.fn` is the original function; attributes set on it (the
  auth policy, `toast_errors`' marker) are readable via
  `cls.event_handlers[name].fn`.
- `rx.event`'s typing: overloads returning `EventCallback[*P]`; a wrapper
  decorator must mirror them or mypy reports `State.handler(arg)` calls in
  components as unbound-method calls. A decorator *under* `rx.event`
  (`toast_errors`) must keep the function's signature — Reflex binds event
  arguments by parameter name.
- Private (`_underscore`) vars are never serialised to the client.
- A state class defined in a test module is an app state to the middleware;
  the policy tests skip it by module name.

## Database

- Since 0.10 `reflex[db]` depends on `greenlet` itself.
- sqlmodel ≥ 0.0.48 maps `datetime` to `UTCDateTime`: binding a naive
  datetime raises; values come back UTC-aware. Use `datetime.now(UTC)`.
- `SAWarning: Table '…' already exists within the given MetaData` during
  `reflex db makemigrations` is the known benign warning.
- `rx.session()` creates a session per call; `utils/db.py:call` runs each
  use case with its own session in a worker thread
  (`asyncio.to_thread`), so nothing a use case returns may be lazily loaded.
- Autogenerate runs with `render_as_batch=True` and `compare_type=False`.
  Adding a foreign key to an **existing** table renders
  `create_foreign_key(None, …)`, which fails on SQLite ("Constraint must
  have a name"): name it by hand in the revision. Column type changes are
  not detected.
