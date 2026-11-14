# Security model

How the generated app implements `architecture.md` on Reflex, and why each
piece exists. Every decision here was asked for by the owner of this skill,
forced by a verified Reflex behaviour (see `reflex_auth_facts.md`), or closes
a weakness found in a production app built with it. Change one only with a
reason at least as strong.

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
  person, two addresses — e.g. after a name change), **delete accounts**
  (their data is handed to another person), **groups**, audit log in the
  database plus structured log events.
- App data has an owner and is shared with people, groups or everyone
  through one implementation (`service/sharing.py`); the service enforces
  every rule with the acting user's id.
- Authorization **like Reflex Enterprise's auth plugin** (secure by default,
  `auth=` checks, `/forbidden`, `redirect_to`), without its OIDC
  authentication.
- **No token or secret in frontend state — only in private (backend) state.**
- Revocation (end session, block) takes effect within 60 seconds.
- Deployment: Docker, one https origin for frontend, backend and WebSocket
  (`reflex run --env prod --single-port`); anything else does not start in
  production.

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

Its *flow* is kept: hashed single-use token, expiry, per-address and per-IP
request limits, and its session lifetime and link limits (7 day sessions,
5 links per window). Two things differ on purpose: links live 15 minutes
(the token is in the query string, so until it is spent it sits in the
browser history and any access log on the way), and a new link does **not**
invalidate earlier ones — see "Nobody can lock another person out".

## The session token

- Created by `auth/endpoints.py` only, as a 256-bit random value, sent once in
  `Set-Cookie`: `HttpOnly`, `SameSite=Lax`, `Path=/`, plus `Secure` and the
  `__Host-` prefix when `api_url` is https.
- Stored server-side as SHA-256 only (`AuthSession.token_hash`).
- Reflex copies the WebSocket handshake headers — `cookie` included — into
  `State.router` on every event. Up to 0.9 it also serialised them to the
  browser (verified then: the token appeared in WebSocket frames); since
  0.10 `cookie` and `authorization` are no longer sent, but on the backend
  `self.router.headers.cookie` still holds the full string, and every other
  handshake header still reaches the browser. `AuthMiddleware` removes the
  session cookie from the router data before any handler runs and keeps only
  its digest in `AuthState._token_hash`. The e2e check "no WebSocket frame
  contains the token" guards this across Reflex upgrades.

## The client token is not a credential

The Reflex client token (a UUID in `sessionStorage`, sent as `?token=` on
the `/_event` socket URL and as a header on uploads) selects the backend
state — `AuthState` included. It must not be enough to act as whoever that
state is signed in as. Two doors were found and closed:

- A browser can add any key to an event's `router_data`; Reflex only
  overwrites `headers`, `sid`, `ip`, `query` and `token`. A flag meaning
  "this copy says nothing about the cookie" could therefore be forged by a
  cookie-less connection that knew a victim's client token.
- `POST /_upload` builds an event from the client-token header alone, with
  no handshake headers at all.

The rule now: **where an event comes from decides what it may say about who
is signed in** (`auth/middleware.py:event_origin`).

| Origin | Recognised by | Identity |
| --- | --- | --- |
| `socket` | `event.router_data` has `headers` (the server puts the handshake's there on every event) | The cookie in it, or its absence, is the truth: resolve, or sign out and reset app states. |
| `chained` | own router data empty; the event context inherits a socket event's and has a parent | Says nothing; the identity stands. |
| `detached` | neither — an HTTP upload | Says nothing; reaches an app handler only with a grant. |

- The "already stripped" flag is a per-process secret compared in constant
  time; a flag from the browser is ignored.
- `auth/upload_gate.py` is ASGI middleware on the `auth_api()` app: a
  `POST /_upload` must come from this app's origin and carry a live session
  cookie (401/403 otherwise). It records a grant "client token X was shown
  session digest Y" for the request plus 30 s; the event middleware lets a
  detached event through only if the state behind X is signed in with Y.
- No socket-id binding is needed: every socket event re-establishes the
  identity from its own handshake, so a second socket without the cookie
  signs the state out on its first event.

Limits, on purpose: on **split origins** (development, ports 3000/8000) the
upload request carries no cookie, so the gate cannot be enforced and stands
aside (`upload_gate.ENFORCED`) — production refuses to start on split
origins. **Upload handlers must not return or yield backend events**: the
grant covers the upload's own event. The grant map is **in memory**; with
several backend workers the upload request and its event are handled by the
same worker, so it holds — re-check if Redis-backed state is introduced.

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
`api_url` (fallback `Sec-Fetch-Site: same-origin|same-site`;
`auth/origin.py`, shared by `/_auth` and the upload gate), and the cookie is
`SameSite=Lax`. CORS (`cors_allowed_origins` in `rxconfig.py`) is those two
origins instead of Reflex's default `*`, for HTTP and the event socket. The confirm page uses `Referrer-Policy: same-origin`
(`no-referrer` makes browsers send `Origin: null`) and a CSP whose
`form-action` names the frontend origin (it also governs the redirect after
the POST).

The admin password form posts directly to the endpoint, so the password
never passes through a Reflex state.

## Authorization (the Enterprise model, rebuilt)

`AuthMiddleware` runs before every event:

1. take the cookie out of the router data of a socket event (see above);
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
| Upload (`detached` event) | 401 at the gate | as an event handler, and only with a grant |
| State field | by convention: only filled by protected handlers | same |

Defaults: every route except `PUBLIC_ROUTES`, every handler of every app
state requires login. `@auth_event(auth=False)` opens a handler,
`@auth_event(auth=check)` restricts it; `ROUTE_CHECKS` restricts routes (the
Enterprise API allows only a bool per page; a per-route check is the minimal
extension needed for an admin area, and it keeps the Enterprise outcome —
`/forbidden`). Checks run only for a signed-in user and fail closed.

Handlers never spell out `auth_event(auth=...)`: `auth/policy.py` defines
one named decorator per check (`admin_event`, `share_owner_event`, …), so a
name cannot mean different checks in different modules.
`tests/test_auth_policy.py` pins the public surface and lists, per state,
the one check its handlers carry and the handlers left to any signed-in
user.

These checks are a **pre-filter**. The rules are enforced in `service/`,
which every handler reaches through `call` (`utils/db.py`) with the acting
user's id — see `architecture.md` section 4 and `tests/test_architecture.py`.

Field protection is by convention, as the owner chose, rather than by
filtering deltas (which would mean patching Reflex's serialisation).

`redirect_to` is accepted only as a same-origin absolute path (no `//`, no
`\`, no scheme/host, no control characters, not `/_auth`), both when the
link is requested and when it is spent.

## Anti-enumeration

The link form shows one message for every outcome; mail is sent off the
event loop so timing does not differ either. Admin login answers "wrong
e-mail or password" for both, and burns a scrypt verification on an unknown
address. The service answers "does not exist or is not shared with you" for
both a missing row and someone else's.

## Limits — and nobody can lock another person out

| Limit | Default | Counts |
| --- | --- | --- |
| `AUTH_LINK_RATE_LIMIT` | 5 | links per address per window |
| `AUTH_LINK_RATE_LIMIT_PER_IP` | 5 | links per client IP per window |
| `AUTH_LINK_REQUESTS_PER_IP` | 30 | link *requests* of any outcome per IP per window |
| `AUTH_ADMIN_MAX_FAILURES_PER_IP` | 5 | failed admin logins per IP per lockout window |
| `AUTH_ADMIN_MAX_FAILURES_GLOBAL` | 20 | failed admin logins from all IPs |

- The link form is public and every request writes an audit row. Past
  `AUTH_LINK_REQUESTS_PER_IP` a request is dropped before any work, with one
  `auth.link_flood` audit row per window — a bounded anonymous write.
- A new link request leaves earlier links valid. Expiring them would let
  anyone who knows an address keep its owner from ever signing in.
- The global admin failure count never locks anyone out by itself — twenty
  wrong guesses from anywhere would otherwise lock the admin out, for free.
  Reaching it allows each IP a single failure per window and audits
  `auth.admin_under_attack` once.

Known and accepted: the limit check and the insert are not one statement, so
two simultaneous requests can exceed a limit by one. `AuthLinkToken.email`
is stored in clear (needed to create the account on redeem) until purged.
The link token is in the query string; moving it to the fragment would need
script on the confirm page, which its CSP (`default-src 'none'`) rules out.

## Admin

Admin is a property of the session (`AuthSession.is_admin`, set only by the
password login). The admin account's addresses never receive magic links,
and it cannot be blocked, merged or deleted. The admin manages accounts,
sessions and groups; there is **no admin bypass** on other people's data in
`service/`. `ADMIN_PASSWORD_HASH` is scrypt
(N=2^17, r=8, p=1) in a `:`-separated format — `$` would be mangled by
docker compose / `.env` interpolation.

## People: merge, delete, groups

App data references `authuser.id`, never an address. Every such column is a
foreign key and is declared as ownership (`OWNER_COLUMNS`, or a `Shareable`'s
owner column) or as a grant (`GRANTEE_COLUMNS`, memberships, shares);
`tests/test_people.py` fails for one that is in neither.

- **Merge** (`auth/service.py:merge_users` → `service/people.py:merge_people`):
  both kinds are re-pointed to the surviving account, after dropping what
  would then exist twice; never a share for the owner of the thing shared.
  Both accounts are signed out everywhere.
- **Delete** (`delete_user` → `hand_over_person`): ownership goes to the
  account the admin picks; grants are dropped, so the heir gains no access
  the deleted person had. The address may sign up again as a new, empty
  account. The audit log keeps the bare id.
- **Groups** are named sets of people managed by the admin; names are
  visible to everyone (to share with), members only to the admin. Deleting a
  group removes its memberships and shares, not what was shared.

## Audit

`auth/service.py:audit()` writes `AuthAuditEvent` rows and a structlog event.
Addresses without an account are stored only as a 16-hex-digit SHA-256
prefix. The audit table is never purged; deciding how long to keep it is
the operator's call. (Apps from scaffold versions before the logging fix
drop `INFO` events, so there only the table records them.)

## Housekeeping

`auth/housekeeping.py` is a Reflex lifespan task: at start and then every
24 hours it deletes link tokens that are spent or expired, sessions that are
revoked or expired, and admin login attempts — each only once older than
`AUTH_PURGE_AFTER_DAYS` (30). Rows inside that window stay for the admin's
session list and for forensics; the lockout window (15 min) is far shorter.
A failed run is logged and retried the next day.

## Known limits

- **Uploads on split origins** (development) are not checked against the
  cookie — see "The client token is not a credential".
- A tab opened before signing in elsewhere stays signed out until it
  reloads; a tab whose session was ended keeps its page until the next event
  after the recheck interval, then is redirected.
- **Split deployments** (frontend and backend on different origins) are not
  supported: the cookie is `SameSite=Lax` and host-only, and
  `auth/settings.py:public_url_problem` stops a production start unless
  `REFLEX_API_URL` and `REFLEX_DEPLOY_URL` are the same `https://` origin
  (loopback hosts are exempt, for health checks and local smoke tests).
- **Reflex version.** The event-origin rules rest on private Reflex
  behaviour verified for 0.10.1. `tests/test_auth_event_origin.py` drives
  the real event processor, so an upgrade that changes it fails there first;
  0.11 is known to differ (see `reflex_auth_facts.md`).
- Rate limits count per client IP. Behind a reverse proxy set
  `AUTH_TRUSTED_PROXIES`, or every user shares the proxy's IP. Many users
  behind one NAT IP share `AUTH_LINK_RATE_LIMIT_PER_IP`.
