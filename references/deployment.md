# Deployment notes

## Docker, one port

```bash
reflex run --env prod --single-port --backend-port 8000 --frontend-port 8000
```

with, in the container environment:

```
REFLEX_DEPLOY_URL=https://app.company.com
REFLEX_API_URL=https://app.company.com
REFLEX_DB_URL=sqlite:////data/reflex.db        # or Postgres; mount a volume
AUTH_ALLOWED_DOMAINS=company.com
ADMIN_EMAIL=…
ADMIN_PASSWORD_HASH=scrypt:…
MAIL_TRANSPORT=graph                           # or smtp / mailgun
```

Both URLs must be the **same public `https://` origin** (no port, no
trailing slash): the cookie becomes `Secure` and `__Host-` prefixed, the
links in e-mails point there, the POST origin check and CORS allow only it,
and uploads can be checked against the session cookie. Anything else —
plain `http://` on a public host, or two different origins — stops the app
at start (`auth/settings.py:public_url_problem`; loopback hosts are exempt
for health checks). Run `reflex db migrate` on start (before `reflex run`).

If the page is served from yet another origin (a tunnel), list every allowed
origin in `REFLEX_CORS_ALLOWED_ORIGINS`.

## Behind a reverse proxy

One site for the whole app — frontend, backend, `/_auth`, `/_upload` and
`/_event` share the port.

- **TLS** terminates at the proxy.
- **WebSocket upgrade** on `/_event` (`Upgrade`/`Connection` passed through,
  read timeout above socket.io's 25 s ping). Without it pages render but
  nothing reacts.
- **Request body size** on `/_upload` as large as the biggest upload
  (nginx: `client_max_body_size`; its default of 1 MB rejects uploads).
- **`X-Forwarded-For`**, and the proxy's address *as the container sees it*
  in `AUTH_TRUSTED_PROXIES` — for a proxy on the same host that is the
  compose network's gateway, not `127.0.0.1`. Without it every sign-in
  counts against the proxy's IP. The admin's session and audit pages show
  the client IP to check it.
- **Keep query strings out of the access log** for `/_event` and
  `/_auth/link` (nginx: a `log_format` with `$uri` instead of `$request` for
  those locations). `/_event?token=…` is the Reflex client token and
  `/_auth/link?t=…` an unspent sign-in link. Neither signs anyone in on its
  own, but neither belongs in a log. (The app itself writes no access log.)
- **Security headers** on every response (the app sends them only on the
  `/_auth` pages). nginx:

  ```nginx
  add_header Strict-Transport-Security "max-age=31536000" always;
  add_header X-Content-Type-Options "nosniff" always;
  add_header Referrer-Policy "same-origin" always;
  add_header Content-Security-Policy-Report-Only "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self' wss://app.company.com; object-src 'none'; base-uri 'none'; frame-ancestors 'none'" always;
  ```

  The policy starts as `-Report-Only` on purpose: click through every page
  with the browser console open. If nothing is reported, rename the header
  to `Content-Security-Policy`; if something is, widen that one directive.
  Do not skip to enforcing — a wrong policy leaves a page that renders and
  does nothing.

  Do **not** force `Referrer-Policy: no-referrer`: browsers then send
  `Origin: null` on the sign-in POSTs and the origin check refuses them
  (`AUTH_ALLOW_NULL_ORIGIN=1` exists for proxies that cannot be changed).

## Backup

Copying a SQLite file while the app writes can catch it half-written. Take a
snapshot with SQLite's online backup API (`sqlite3.Connection.backup`) and
back up the snapshot; with Postgres use `pg_dump`.

## Mail

| Transport | Use when |
| --- | --- |
| `graph` | Company Microsoft 365 tenant; no SMTP AUTH needed. App registration with **Application** permission `Mail.Send`, admin consent, and an application access policy limiting it to the sending mailbox. |
| `smtp` | Any mailbox with SMTP AUTH, e.g. `smtp.office365.com:587` `starttls` (often disabled in M365 tenants), or an internal relay (`SMTP_SECURITY=none`). |
| `mailgun` | Mailgun account; EU region uses `https://api.eu.mailgun.net`. |
| `console` | Local development only; refused when `REFLEX_ENV_MODE=prod`. |

Variables per transport: `auth/mail/__init__.py` and `.env.example`.

## Admin password

```bash
uv run python -m <app>.auth.hash_password
```

Paste the printed `scrypt:…` value as `ADMIN_PASSWORD_HASH`. It contains no
`$`, so it is safe in compose files and `.env`. Change the password by
replacing the hash and restarting.
