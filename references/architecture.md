# Architecture of a secure multi-user app

The rules below hold for any application in which several people sign in and
own data — whatever the framework. They were worked out on a production app
and each one closes a hole that was actually found there. The templates of
this skill are their implementation for Reflex; `security_model.md` explains
the Reflex-specific mechanics.

Use this file in three ways: as the design to follow when building on a
generated app, as the checklist when reviewing one (section 9), and as the
specification when the same architecture is needed on another stack.

## The shape

```
browser ──HTTP──▶ sign-in / sign-out endpoints ──▶ session cookie (HttpOnly)
   │
   └─events/requests──▶ gate ──▶ handler ──▶ service (use case, actor id) ──▶ database
                         │          │              │
                    who is this?  declared      checks again,
                    may they      policy,       returns plain values
                    call this?    no `if`
```

Four layers, each with one job:

| Layer | Job | Never does |
| --- | --- | --- |
| **Identity** (sign-in endpoints, session store) | Turn a credential into a server-side session. | Hand a secret to script in the page. |
| **Gate** (middleware in front of every handler) | Establish who is calling, on every call; apply the declared policy. | Trust anything the client says about who it is. |
| **Handlers** (UI events, API routes) | Translate input, call one use case, show the outcome. | Decide who may do what; query the database. |
| **Service** (use cases) | Enforce the rules with the acting user's id; own every query. | Know the UI or the web framework. |

## 1. Identity: the session

1. **One credential, and script cannot read it.** The session token is a
   256-bit random value in an `HttpOnly`, `SameSite=Lax`, `Secure`,
   host-only (`__Host-`) cookie. It is set and cleared only by HTTP
   responses of the sign-in and sign-out endpoints. It never appears in
   application state, local storage, a URL, a log line or an error message.
2. **The server stores a digest, not the token.** A database leak then
   yields no usable sessions. Compare in constant time.
3. **Nothing else works as a credential.** Every other identifier the client
   holds — a tab id, a client token, a websocket session id, a key in a
   request body — only *selects* state; it never proves who someone is. If
   knowing such a value is enough to act as someone, it is a second,
   unprotected credential. Decide for every way a request can arrive
   (socket, plain HTTP, upload, background task, chained event) what it may
   say about the caller's identity; the default is "nothing".
4. **Sessions are revocable and re-checked.** The identity cached for a
   connection is re-read from the database on every navigation and at least
   every N seconds (60), so ending a session or blocking an account takes
   effect within that bound. Expiry is enforced by the server.
5. **A change of identity resets state.** When the signed-in user behind a
   connection changes (sign-out, another account), everything held for the
   previous one is discarded before anything else runs.
6. **Links and redirects come from server configuration.** Never build an
   absolute URL from `Host`, `Origin`, `window.location` or any other value
   the client supplies — otherwise the server mails a real token pointing at
   an attacker's origin. A post-login redirect target is a same-origin path,
   validated when stored and again when used.
7. **State-changing requests prove their origin.** Every POST checks
   `Origin` (fallback `Sec-Fetch-Site`) against the app's own configured
   origins, in addition to `SameSite`. CORS allows those origins only, not
   `*`.
8. **GET never spends a token.** Mail scanners and link previews fetch every
   link. A sign-in link's GET shows a confirmation page; the POST behind its
   button redeems the token — once, atomically, and only while unexpired.

## 2. Sign-in without leaking who exists

1. **One answer for every outcome.** The public sign-in form says the same
   thing for a known address, an unknown one, a blocked account, a foreign
   domain and a rate-limited request, and takes the same time (send mail off
   the request path; verify a dummy hash for unknown users).
2. **Rate limits on every public write**, per account *and* per client
   address, and a cap on requests of any outcome — a public form that
   writes an audit row per request is otherwise an unbounded write.
3. **Nobody can lock another person out.** A limit that counts across all
   clients must never deny service to a client that has not misbehaved
   itself: requesting a new link does not invalidate earlier ones; a global
   failure count tightens the per-client limit instead of locking the
   account.
4. **Client addresses are only as good as the proxy configuration.**
   `X-Forwarded-For` is believed only from explicitly trusted proxies;
   otherwise every limit can be evaded or everyone shares one bucket.
5. **Privilege is a property of the session, not of the account.** An
   administrator signs in through a separate, stronger path (password with a
   memory-hard hash from the environment, at an unlinked route); the same
   person signing in the ordinary way gets an ordinary session. Privilege is
   never derived from an e-mail address or a client-supplied flag.

## 3. Authorization: declared, default-deny

1. **Everything requires a signed-in user unless it is explicitly opened.**
   A new page or handler is protected without anyone doing anything. The
   public surface is a short list in one file, pinned by a test, so widening
   it is a deliberate, reviewable change.
2. **Rules are declared on the surface they protect**, as named checks
   (`is_admin`, `owns_open_document`) attached to routes and handlers —
   never as `if` statements inside handlers, where they are forgotten in the
   next handler. One name means one check everywhere. A test lists, per
   module, which handlers are deliberately left to any signed-in user.
3. **Checks fail closed.** A check that raises denies.
4. **Hiding is not enforcing.** Whether a control is shown is presentation;
   the check on the handler behind it is what protects. Every hidden control
   needs both.
5. **Protected data is loaded only by protected handlers**, and state has
   presentable defaults — that is what a signed-out client holds.
6. **Every way a page opens goes through the gate** — first load,
   client-side navigation, reconnect — whether or not the page loads data.
   A gate hooked to "the page's load handler" misses pages that have none.

## 4. The service is the gate

The declared checks decide whether a handler may be *called*. They are a
pre-filter: cheap, close to the UI, and bypassable by any second caller (a
script, an API, a background job, the next refactor). The rules themselves
live one layer down.

1. **Every use case takes the acting user's id** as an explicit argument and
   checks what that user may see or do. The id comes from the identity the
   gate established — never from a request parameter.
2. **Reads are checked like writes.** "What a screen shows" is one function
   that takes the viewer and returns only what the viewer may see. A list is
   always a query filtered by a visibility predicate, never a bare
   `select *` filtered afterwards.
3. **"Missing" and "not yours" give the same answer**, so existence is not
   leaked through error messages or status codes.
4. **Handlers do not query.** They hand a use case to one helper that opens
   the session (and runs it off the event loop). An architecture test fails
   on a query, a session or a table import outside the service. This is what
   makes "who may see what" answerable by reading one package.
5. **Plain values cross the boundary, not table rows.** A read model
   contains the fields a screen needs; adding a column to a table changes
   nothing a client sees until it is added on purpose. This prevents
   accidental disclosure and is also the contract a later API or a second
   client is written against.
6. **Refusals are exceptions with a user-safe message** (`PermissionDenied`,
   `DomainError`). Handlers let them rise; one decorator turns them into the
   error message shown. Anything else is a bug and propagates. Ids from the
   client are parsed by one function that refuses instead of raising from
   deep inside a handler.
7. **The service does not import the UI or the web framework.** It is the
   backend contract and must be callable from a script, a worker or a test
   with nothing but a database session.

## 5. Ownership and sharing

1. **Everything a person creates has exactly one owner**, stored as the
   account id. Only the owner changes, shares or deletes it.
2. **Sharing is implemented once**, generically: with a person, with a group
   (every present and future member), with everyone. A new shareable kind is
   a declaration plus two tables, never a copy of the functions — copies
   drift, and the drift is a permission bug.
3. **Sharing grants reading.** Whatever more it grants (copying, commenting)
   is a rule of that kind, built on the same visibility predicate. A copy is
   a new thing with the copier as its only owner.
4. **Only the owner sees who else has access.** Group names are visible to
   share with; group members are visible only to whoever manages groups.
5. **No administrator bypass by default.** The administrator manages
   accounts, sessions and groups — not other people's data. If the app needs
   support access, make it an explicit, audited rule, not a side effect.

## 6. People change

1. **A person is an account id, never an e-mail address.** Addresses change,
   and one person ends up with two accounts.
2. **Every column that holds a person is declared** as either *ownership*
   (what they made) or *grant* (access given to them), and a test fails for
   an undeclared one.
3. **Merging two accounts** re-points both kinds to the surviving account,
   dropping what would then exist twice (one membership per group, one share
   per thing, never a share with the owner) — in one transaction, with every
   session of both accounts ended.
4. **Deleting an account** hands ownership to a chosen person and *drops*
   grants: the heir must not silently gain access the deleted person had.
5. **Blocking** ends every session and refuses new ones, without deleting
   anything.

## 7. Secrets, configuration, audit

1. **Secrets live in the environment of the backend** and nowhere else — not
   in the repository, not in client state, not in an image layer. Whatever
   the framework sends to the client is treated as public.
2. **A bad configuration value stops the app at start** rather than quietly
   weakening it: an unparsable limit, plain HTTP in production, split
   origins, a development mail transport in production.
3. **Security events are audited** in the database (who, what, when, from
   where) and as structured log events. Addresses that belong to no account
   are stored only as a digest. Refusals are logged: one nobody expected is
   a bug report.
4. **Dead rows are purged** on a schedule (spent links, ended sessions, old
   attempts); how long the audit log is kept is the operator's decision.
5. **No phoning home.** No telemetry, CDN assets or third-party calls unless
   the project asks for them.

## 8. Deployment

1. **One HTTPS origin** for pages, API, uploads and sockets. It makes the
   cookie `Secure` and host-only, and lets every request be checked against
   the same session.
2. **The reverse proxy** forwards websocket upgrades, sets
   `X-Forwarded-For`, keeps query strings of token-bearing URLs out of its
   access log, and sends the security headers (HSTS, `nosniff`,
   `Referrer-Policy`, a CSP introduced as report-only first).
3. **Backups are consistent snapshots**, not copies of a live database file.

## 9. Review checklist

Ask these of any change to a multi-user app:

- Is there a new way for a request to reach a handler? What does it prove
  about the caller? (1.3)
- Does any new value in client state, a URL, a log or an error message
  derive from a secret? (1.1, 7.1)
- Is a new page or handler public? Is that in the pinned list? (3.1)
- After a framework upgrade: is every way a page opens, and every way a
  handler is reached, still behind the gate? (1.3, 3.6)
- Does a new handler carry the named check for what it changes, and does the
  use case it calls check again with the actor's id? (3.2, 4.1)
- Does a new read go through a function that takes the viewer? (4.2)
- Does a new error distinguish "missing" from "not yours"? (4.3)
- Does a new table hold a person? Is the column declared as ownership or
  grant, and do merge and delete handle it? (6.2)
- Does a new public form write to the database? What bounds it? (2.2)
- Can one user's action deny service to another? (2.3)
- Is a new absolute URL built from configuration only? (1.6)

## Where each rule lives in a generated app

| Rule | Code | Guard |
| --- | --- | --- |
| 1.1–1.2 cookie, digest | `auth/endpoints.py`, `auth/cookie.py`, `auth/security.py` | `tests/test_auth_security.py` |
| 1.3 what an event proves | `auth/middleware.py:event_origin`, `auth/upload_gate.py` | `tests/test_auth_event_origin.py`, `test_auth_upload_gate.py` |
| 1.4–1.5 recheck, reset | `auth/middleware.py` | `tests/test_auth_middleware.py` |
| 1.6–1.8 URLs, origin, GET/POST | `auth/security.py`, `auth/origin.py`, `auth/endpoints.py`, `rxconfig.py` | `tests/test_auth_security.py`, `test_auth_origin.py` |
| 2 sign-in, limits, admin | `auth/service.py`, `auth/settings.py` | `tests/test_auth_service.py` |
| 3 declared policy | `auth/policy.py`, `auth/authz.py` | `tests/test_auth_policy.py` |
| 4 service is the gate | `service/`, `utils/db.py`, `states/handlers.py` | `tests/test_architecture.py`, `test_handlers.py`, `test_service_layout.py` |
| 5 ownership, sharing | `service/sharing.py`, `service/groups.py`, `states/share_state.py` | `tests/test_sharing.py`, `test_groups.py`, `test_share_state.py` |
| 6 merge, delete | `service/people.py`, `auth/merge_hooks.py`, `auth/service.py` | `tests/test_people.py`, `test_auth_service.py` |
| 7 settings, audit, purge | `auth/settings.py`, `auth/service.py`, `auth/housekeeping.py` | `tests/test_auth_security.py`, `test_auth_service.py` |
