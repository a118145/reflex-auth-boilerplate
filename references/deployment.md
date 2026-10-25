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

Both URLs must be the public HTTPS origin: the cookie becomes `Secure` and
`__Host-` prefixed when `REFLEX_API_URL` is https, and the links in e-mails
point there. Run `reflex db migrate` on start (before `reflex run`).

Verified for this skill: prod + single port, full sign-in/admin flow, with
the Mailgun transport against a local fake API.

## Behind a reverse proxy

Terminate TLS at the proxy, forward WebSocket upgrades, and set
`AUTH_TRUSTED_PROXIES` to the proxy's IP(s) so rate limits and the audit log
see real client addresses. Without it every request counts against the
proxy's IP.

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
