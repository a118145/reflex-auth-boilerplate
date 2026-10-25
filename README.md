# reflex-auth-boilerplate

A [Claude Code](https://claude.com/claude-code) skill that adds
authentication and authorization to a [Reflex](https://reflex.dev) app
created with the
[reflex-app-scaffold](https://github.com/a118145/reflex-app-scaffold) skill.

## What it adds

- **Magic-link sign-in** for addresses on allowed e-mail domains. Accounts
  are created on first sign-in.
- **Every page and event protected** by default; only a public landing page
  (logo, slogan, sign-in form — no navigation), the admin login and
  `/forbidden` are open. Login redirects keep `redirect_to`.
- **One admin** with e-mail + password from the environment (scrypt hash),
  at an unlinked route, with per-IP and global lockout.
- **Admin area**: live sessions (end them), accounts (block, merge two
  addresses into one person), audit log.
- **Authorization modelled on Reflex Enterprise's auth**: secure by
  default, `@auth_event(auth=check)`, route checks, `/forbidden`, state reset
  on user change — without `reflex-enterprise`.
- Mail via **Microsoft Graph**, **SMTP**, **Mailgun**, or console (dev).
- The account block (address, log out, log out everywhere) at the end of the
  navigation in all three scaffold layouts.

## Security in one paragraph

The session token lives only in an HttpOnly, SameSite=Lax cookie set by
backend endpoints; the server stores its SHA-256. Reflex 0.9.8 serialises
the WebSocket handshake headers — cookies included — into `State.router` and
sends them to the browser; an event middleware strips the cookie before
that happens. Magic links sign in on POST, not GET, so mail scanners cannot
spend them. Links and redirects are built from server configuration only.
Details: [`references/security_model.md`](references/security_model.md).

## Install

```bash
git clone https://github.com/a118145/reflex-auth-boilerplate \
  ~/.claude/skills/reflex-auth-boilerplate
```

Then, in a scaffold-generated app, ask Claude Code to add authentication.

## Verified against

Reflex 0.9.8, sqlmodel 0.0.48. Applied to fresh scaffold apps in all six
combinations (layouts `both`/`top`/`side` × database yes/no): ruff, mypy
(strict) and the generated tests pass, and the app compiles without
deprecation warnings. A 34-step browser test (sign-in, redirects, cookie
flags, no token in WebSocket frames, forbidden pages, admin login and
lockout, session revocation, logout, merge, block, audit, CSRF refusal)
passed on all three layouts in dev mode and in prod `--single-port` mode.

## Layout

```
SKILL.md        the procedure Claude follows
references/     security model, verified Reflex facts, deployment, AGENTS.md block
templates/      files copied into the app (auth/, pages, states, ui, tests)
snippets/       exact insertions into the scaffold's files
```
