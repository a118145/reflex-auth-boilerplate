# Security model

Why each piece exists. Every decision here was asked for by the owner of this
skill or forced by a verified Reflex behaviour (see
`reflex_098_auth_facts.md`). Change one only with a reason at least as strong.

## Requirements this implements

- Magic-link sign-in, restricted to an e-mail **domain allowlist**
  (`AUTH_ALLOWED_DOMAINS`, exact match).
- **Every page is protected**, no exceptions, except a public landing page
  without navigation (slogan, logo, sign-in form), the unlinked admin login
  and `/forbidden`.
- **One admin**, configured by environment (`ADMIN_EMAIL`,
  `ADMIN_PASSWORD_HASH`), signs in with a password only. Brute-force
  protection per IP and globally.
- Admin area: see and end sessions, block accounts, **merge accounts** (one
  person, two addresses — e.g. after a name change), audit log in the
  database plus structured log events.
- Authorization **like Reflex Enterprise's auth plugin** (secure by default,
  `auth=` checks, `/forbidden`, `redirect_to`), without its OIDC
  authentication.
- **No token or secret in frontend state — only in private (backend) state.**
- Revocation (end session, block) takes effect within 60 seconds.
- Deployment: Docker, one port for frontend and WebSocket
  (`reflex run --env prod --single-port`).

## Why not `reflex-magic-link-auth` or `reflex-enterprise`

`reflex-enterprise`'s `AuthPlugin` only authenticates via OIDC providers
(`OIDCAuthState`), and the package is proprietary (EULA, Reflex Cloud token).
Its *authorization model* is reproduced here instead.

`reflex-magic-link-auth` 0.2.2 was reviewed and **not used**, because:

| Finding | Consequence |
| --- | --- |
| `session_token` is `rx.LocalStorage(sync=True)` | token readable by JavaScript |
| `auth_session` is a public computed var holding `session_token`, `email`, `persistent_id` | token serialised to the client |
| auth page does `rx.redirect(redir)` unchecked | open redirect |
| link base URL comes from `window.location.origin` (client) | attacker can make the server mail a real token for the victim's address pointing at the attacker's origin |
| page registered on `import` | importing the models adds the vulnerable route |
| 32-bit OTP, no rate limit on verification | weak |
| `rx.Model` | deprecated in 0.9 (scaffold requires zero deprecations) |
| sessions keyed on e-mail | no account merging |

Its *flow* is kept: hashed single-use token, expiry, "only one live link per
address", per-address and per-IP request limits, and its defaults (30 min
links, 7 day sessions, 5 links per window).

## The session token

- Created by `auth/endpoints.py` only, as a 256-bit random value, sent once in
  `Set-Cookie`: `HttpOnly`, `SameSite=Lax`, `Path=/`, plus `Secure` and the
  `__Host-` prefix when `api_url` is https.
- Stored server-side as SHA-256 only (`AuthSession.token_hash`).
- **Reflex copies the WebSocket handshake headers — `cookie` included — into
  `State.router` and sends them to the browser in every delta.** Without
  countermeasure, an HttpOnly cookie is readable through the Reflex state
  (verified: the token appeared in WebSocket frames). `AuthMiddleware` removes
  the cookie from the router data before any delta is built and keeps only
  its digest in `AuthState._token_hash`. The e2e check "no WebSocket frame
  contains the token" guards this.

## Signing in and out

A Reflex event cannot set an HttpOnly cookie, so these are plain HTTP:

| Route | |
| --- | --- |
| `GET /_auth/link?t=…` | Minimal HTML page with a *Sign in* button. Read-only. |
| `POST /_auth/link` | Spends the token atomically, creates the account on first use, sets the cookie, 303 → `redirect_to`. |
| `POST /_auth/admin-login` | Lockout check, scrypt verify (dummy verify for unknown addresses), cookie, 303. |
| `POST /_auth/logout` | Revokes this session (or all with `everywhere=1`), clears the cookie, 303 → `/login`. |

The GET/POST split exists because corporate mail scanners (Outlook Safe
Links) fetch every link in a mail. A GET that signed in would let the scanner
spend — or use — the token.

CSRF: every POST must carry an `Origin` of the app's own `deploy_url` or
`api_url` (fallback `Sec-Fetch-Site: same-origin|same-site`), and the cookie
is `SameSite=Lax`. The confirm page uses `Referrer-Policy: same-origin`
(`no-referrer` makes browsers send `Origin: null`) and a CSP whose
`form-action` names the frontend origin (it also governs the redirect after
the POST).

The admin password form posts directly to the endpoint, so the password
never passes through a Reflex state.

## Authorization (the Enterprise model, rebuilt)

`AuthMiddleware` runs before every event:

1. take the cookie out of the router data (see above);
2. resolve the session when the cookie changed, on every page load, and
   otherwise when the last check is older than `AUTH_SESSION_RECHECK_SECONDS`
   (60) — this bounds how long an ended session or blocked account keeps
   working;
3. when the signed-in user changes, **reset every app state** (Enterprise:
   "logout resets protected state");
4. apply `auth/policy.py`:

| Surface | Not signed in | Check fails |
| --- | --- | --- |
| Page (`on_load_internal`) | redirect `/login?redirect_to=<path>` | redirect `/forbidden` |
| Event handler | redirect `/login` | "Action not allowed" toast, handler not run |
| State field | by convention: only filled by protected handlers | same |

Defaults: every route except `PUBLIC_ROUTES`, every handler of every app
state requires login. `@auth_event(auth=False)` opens a handler,
`@auth_event(auth=check)` restricts it; `ROUTE_CHECKS` restricts routes (the
Enterprise API allows only a bool per page; a per-route check is the minimal
extension needed for an admin area, and it keeps the Enterprise outcome —
`/forbidden`). Checks run only for a signed-in user and fail closed.

Field protection is by convention, as the owner chose, rather than by
filtering deltas (which would mean patching Reflex's serialisation).

`redirect_to` is accepted only as a same-origin absolute path (no `//`, no
`\`, no scheme/host, no control characters, not `/_auth`), both when the
link is requested and when it is spent.

## Anti-enumeration

The link form shows one message for every outcome; mail is sent off the
event loop so timing does not differ either. Admin login answers "wrong
e-mail or password" for both, and burns a scrypt verification on an unknown
address.

## Admin

Admin is a property of the session (`AuthSession.is_admin`, set only by the
password login). The admin account's addresses never receive magic links,
and it cannot be blocked or merged. `ADMIN_PASSWORD_HASH` is scrypt
(N=2^17, r=8, p=1) in a `:`-separated format — `$` would be mangled by
docker compose / `.env` interpolation.

## Audit

`auth/service.py:audit()` writes `AuthAuditEvent` rows and a structlog event.
Addresses without an account are stored only as a 16-hex-digit SHA-256
prefix. Note: the scaffold's `utils/logging.py` routes structlog through the
stdlib logger without configuring a handler, so `INFO` events are not
printed by default — the database table is the reliable record.

## Known limits

- **Uploads** (`rx.upload`) reach handlers through `/_upload` without
  handshake headers; they are authorized by the identity cached for that
  browser tab (re-checked every 60 s). Whoever holds the tab's Reflex client
  token (sessionStorage) can use it — the same trust Reflex itself places in
  that token.
- A tab opened before signing in elsewhere stays signed out until it
  reloads; a tab whose session was ended keeps its page until the next event
  after the recheck interval, then is redirected.
- **Split deployments** (frontend and backend on different sites) are not
  supported: the cookie is `SameSite=Lax` and host-only.
- Rate limits count per client IP. Behind a reverse proxy set
  `AUTH_TRUSTED_PROXIES`, or every user shares the proxy's IP. Many users
  behind one NAT IP share `AUTH_LINK_RATE_LIMIT_PER_IP`.
