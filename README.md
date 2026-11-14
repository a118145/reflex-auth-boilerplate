# reflex-auth-boilerplate

A [Claude Code](https://claude.com/claude-code) skill for building **secure
multi-user apps**. It carries two things:

- **An architecture** — [`references/architecture.md`](references/architecture.md):
  framework-neutral rules for any app in which several people sign in and
  own data (session, sign-in, declared authorization, the service as the
  gate, ownership and sharing, merging and deleting accounts, deployment),
  with a review checklist. Derived from a production app; each rule closes a
  hole that was found there.
- **Its implementation for [Reflex](https://reflex.dev)** — templates that
  retrofit it onto an app created with the
  [reflex-app-scaffold](https://github.com/a118145/reflex-app-scaffold)
  skill.

## What it adds to an app

- **Magic-link sign-in** for addresses on allowed e-mail domains. Accounts
  are created on first sign-in.
- **Every page and event protected** by default; only a public landing page
  (logo, slogan, sign-in form — no navigation), the admin login and
  `/forbidden` are open. Login redirects keep `redirect_to`.
- **One admin** with e-mail + password from the environment (scrypt hash),
  at an unlinked route. Guessing is limited per IP; nobody can lock the
  admin — or any user — out.
- **Admin area**: dashboard, accounts (block, merge two addresses into one
  person, delete with hand-over of data), groups, live sessions (end them),
  audit log.
- **Declared authorization**: secure by default, named decorators per check,
  route checks, `/forbidden`, state reset on user change.
- **A service layer**: every use case takes the acting user's id and checks
  what that user may see or do; states reach the database only through it
  and get plain values back.
- **Ownership and sharing, written once**: a table becomes owned and
  shareable — with a person, a group, everyone — by declaring a `Shareable`;
  merge and delete of accounts follow automatically.
  [`references/ownership_and_sharing.md`](references/ownership_and_sharing.md)
  is the recipe.
- **Guard tests** (about 200) that keep the architecture: the public
  surface, which handlers carry which check, no query outside the service,
  every person column covered by merge and delete, what an event may say
  about who is signed in.
- Mail via **Microsoft Graph**, **SMTP**, **Mailgun**, or console (dev).
- A daily clean-up of spent links, ended sessions and old login attempts
  (the audit log is kept).

## Security in one paragraph

The session token lives only in an HttpOnly, SameSite=Lax cookie set by
backend endpoints; the server stores its SHA-256. The Reflex client token is
not a credential: only an event that arrived on a socket, with that socket's
handshake cookie, says who is signed in, and uploads need a grant from a gate
that checks the cookie on the HTTP request. Magic links sign in on POST, not
GET, so mail scanners cannot spend them. Links and redirects are built from
server configuration only; POSTs and CORS accept the app's own origin only.
Production starts on one https origin or not at all. The rules themselves
are enforced in the service, with the acting user's id — the UI checks are a
pre-filter. Details: [`references/security_model.md`](references/security_model.md).

## Install

```bash
git clone https://github.com/a118145/reflex-auth-boilerplate \
  ~/.claude/skills/reflex-auth-boilerplate
```

Then, in a scaffold-generated app, ask Claude Code to add authentication or
to make the app multi-user. For a design review of any multi-user app, ask
it to check the app against the skill's architecture.

## Verified against

**Reflex 0.11.0** (pinned by the skill), sqlmodel 0.0.50, with the current
reflex-app-scaffold. Applied to a fresh scaffold app (layout `both`, with
database): ruff, mypy (strict) and the generated tests pass, and the app
compiles without deprecation warnings. Browser tests passed in dev mode
**and in prod `--single-port` mode** for: signed-out redirects (also for
pages without on_load handlers and unknown paths), sign-in and
`redirect_to`, cookie flags, no token in WebSocket frames, forbidden pages,
admin login, groups, users, sessions, audit, CSRF refusal, logout, and the
upload gate answering 401/403 in front of Reflex's own `/_upload`. After
applying the ownership recipe to the scaffold's CRUD demo, two users sharing
an item was tested in dev mode (invisible before, readable after, no edit
controls and no share card for the reader).

The move from 0.10.1 to 0.11.0 was verified by diffing the two releases'
event, state, config and upload code; what changed is listed in
[`references/reflex_auth_facts.md`](references/reflex_auth_facts.md).

Not re-verified on 0.11.0: layouts `top` and `side`, and the database-less
path (their wiring steps are unchanged; the latter was verified on 0.10.1).

## Layout

```
SKILL.md        the procedure Claude follows
references/     architecture, security model, verified Reflex facts,
                ownership recipe, deployment, AGENTS.md block
templates/      files copied into the app (auth/, service/, states, pages,
                components, ui, utils, tests)
snippets/       exact insertions into the scaffold's files
```

## License

MIT — see [LICENSE](LICENSE).
