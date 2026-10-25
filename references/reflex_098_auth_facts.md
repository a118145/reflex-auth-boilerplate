# Reflex 0.9.8 — facts this skill depends on

Each one verified against the installed package source and, where marked,
in a running app. Re-verify after a Reflex upgrade; several are private
behaviour.

## Router data reaches the browser — including cookies

`App` socket handler builds `router_data["headers"]` from the WebSocket
handshake (`environ["asgi.scope"]["headers"]`) for every event.
`State.router` (`RouterData`) is a normal field, and
`serialize_router_data` includes `headers` — every header incl. `cookie` and
`raw_headers`. **Verified in a browser: an HttpOnly cookie's value appears in
the WebSocket frames.** Hence `AuthMiddleware` strips it.

`State.router_data` itself is `is_var=False` (not sent). Events Reflex chains
on the backend (`on_load` handlers built in `OnLoadInternalState`,
handler-returned events) are built with `router_data=self.router_data`, i.e.
the already stripped copy — so "no cookie in router data" does not mean
"signed out" for those. The middleware flags stripped data
(`_auth_cookie_stripped`).

`router_data["headers"]["asgi-scope-client"]` is the real socket peer;
`router.session.client_ip` blindly trusts `X-Forwarded-For`.

## Event middleware

`reflex.middleware.middleware.Middleware` (import from that module; the
package does not re-export it explicitly for mypy) with
`async preprocess(app, state, event) -> StateUpdate | None`.
`app.add_middleware(mw, index=0)`. Called in
`BaseStateEventProcessor._execute_event` with the **root state**, after
`state.router_data`/`state.router` were set from the event and **before** the
handler runs or any delta is computed. Returning a `StateUpdate` skips the
handler; its `events` are sent (`Event.from_event_type(rx.redirect(...))`).
Not deprecated. Applies to hydrate, `on_load_internal`, user handlers, and
upload handlers (`/_upload` enqueues through the same processor, with empty
router data).

Page loads arrive as `<OnLoadInternalState full name>.on_load_internal`;
`state.router.route_id` is the matched route pattern (e.g. `/data/[item_id]`,
`/404` for unknown paths).

## HTTP routes next to the app

`rx.App(api_transformer=Starlette(routes=[...]))`: Reflex adds CORS and
mounts itself below at `""`, so these routes win. Same path with different
methods works (Starlette prefers the full method match). In dev the backend
is `api_url` (`:8000`) and the frontend dev server (`:3000`) does **not**
proxy backend paths — links and form actions must use `api_url`. Cookies are
not port-bound, so a cookie set by `localhost:8000` is sent to the
`localhost:3000` page and its WebSocket to `:8000` (same site).

`--single-port` requires `--env prod`; set `REFLEX_DEPLOY_URL` and
`REFLEX_API_URL` to the same public URL. The prod static server redirects
`/data` → `/data/` (307).

## Forms

`rx.form` **and** `rx.el.form` always attach an `onSubmit` that calls
`preventDefault` (`Form.create` installs `prevent_default` when no
`on_submit` is given) — a native POST to a backend URL is impossible with
them. `components/native_form.py` is a bare `rx.Component` with
`tag = "form"` and `_is_tag_in_global_scope = True` (how `rx.el.*` render a
string tag; without it the production build fails with
`ReferenceError: form is not defined`, while dev mode hides it).

`rx.input(auto_complete=...)` is a **bool** on Radix TextField; pass the HTML
attribute via `custom_attrs={"autoComplete": "email"}`.

## State

- `State.reset()` resets base and backend vars (not `router`) and recurses
  into **loaded** substates only; to reset everything, `get_state` each class
  (`cls.get_substates()` recursively).
- `State(**{"_reflex_internal_init": True})` builds a root state in tests.
- `EventHandler.fn` is the original function; attributes set on it (the
  auth policy) are readable via `cls.event_handlers[name].fn`.
- `rx.event`'s typing: overloads returning `EventCallback[*P]`; a wrapper
  decorator must mirror them or mypy reports `State.handler(arg)` calls in
  components as unbound-method calls.

## Database

- `reflex[db]` does not install `greenlet`, which `reflex.model` needs
  (`sqlalchemy.ext.asyncio`): `reflex init` fails on a fresh install until
  `uv add greenlet`.
- sqlmodel ≥ 0.0.48 maps `datetime` to `UTCDateTime`: binding a naive
  datetime raises; values come back UTC-aware. Use `datetime.now(UTC)`.
- `SAWarning: Table '…' already exists within the given MetaData` during
  `reflex db makemigrations` is the known benign warning.
