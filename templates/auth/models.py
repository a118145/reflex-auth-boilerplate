"""Auth tables.

An account (``AuthUser``) is separate from its addresses (``AuthUserEmail``),
so two addresses can belong to one person — that is what makes merging
accounts possible. App tables that belong to a person reference
``authuser.id``, never an e-mail address; ``auth/merge_hooks.py`` re-points
them when accounts are merged.

No secret is stored in plain text: link tokens and session tokens are kept as
SHA-256 digests (both are 256-bit random values, so a fast hash is enough),
and the admin password lives only in the environment as a scrypt hash.

All timestamps are timezone-aware UTC. SQLite drops the zone on read, so
``utc()`` restores it before comparing.
"""

from datetime import UTC, datetime

from reflex.model import ModelRegistry
from sqlmodel import Field, SQLModel


def now() -> datetime:
    return datetime.now(UTC)


def utc(value: datetime) -> datetime:
    """Re-attach UTC to a datetime SQLite handed back naive."""
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


@ModelRegistry.register
class AuthUser(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=now)
    last_login_at: datetime | None = Field(default=None)
    blocked_at: datetime | None = Field(default=None)


@ModelRegistry.register
class AuthUserEmail(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="authuser.id", index=True)
    # Stored lower-cased; the unique index is what stops one address from
    # belonging to two accounts.
    email: str = Field(unique=True, index=True)
    created_at: datetime = Field(default_factory=now)


@ModelRegistry.register
class AuthLinkToken(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(index=True)
    token_hash: str = Field(unique=True, index=True)
    redirect_to: str = Field(default="/")
    client_ip: str = Field(default="", index=True)
    created_at: datetime = Field(default_factory=now, index=True)
    expires_at: datetime
    used_at: datetime | None = Field(default=None)


@ModelRegistry.register
class AuthSession(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="authuser.id", index=True)
    token_hash: str = Field(unique=True, index=True)
    # The address this session signed in with — what the UI shows.
    email: str
    # Only a password login creates an admin session; a magic link never does.
    is_admin: bool = Field(default=False)
    client_ip: str = Field(default="")
    user_agent: str = Field(default="")
    created_at: datetime = Field(default_factory=now)
    expires_at: datetime
    revoked_at: datetime | None = Field(default=None)


@ModelRegistry.register
class AuthLoginAttempt(SQLModel, table=True):
    """Admin password attempts, for the per-IP and global lockout."""

    id: int | None = Field(default=None, primary_key=True)
    client_ip: str = Field(index=True)
    success: bool
    created_at: datetime = Field(default_factory=now, index=True)


@ModelRegistry.register
class AuthAuditEvent(SQLModel, table=True):
    """Security events, shown to the admin.

    User ids are plain integers rather than foreign keys: merging deletes the
    source account, and its history must survive that. Addresses that do not
    belong to an account are recorded only as a digest.
    """

    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=now, index=True)
    event: str = Field(index=True)
    actor_user_id: int | None = Field(default=None)
    subject_user_id: int | None = Field(default=None, index=True)
    email_hash: str = Field(default="")
    client_ip: str = Field(default="")
    detail: str = Field(default="")


AUTH_TABLES = [
    AuthUser,
    AuthUserEmail,
    AuthLinkToken,
    AuthSession,
    AuthLoginAttempt,
    AuthAuditEvent,
]
