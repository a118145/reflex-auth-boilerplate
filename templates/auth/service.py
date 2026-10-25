"""Every auth database operation, as plain functions over a ``Session``.

No Reflex state and no HTTP in here: endpoints, the middleware and the admin
state call these, and tests call them against a throwaway database. Each
function commits its own work.

Outcomes that the outside world must not be able to tell apart (unknown
address, foreign domain, blocked account, rate limit) are distinguished here
for the audit log only — callers show the same message for all of them.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta
from typing import Literal

from sqlalchemy import ColumnElement, delete, func, or_, update
from sqlmodel import Session, col, select

from ..utils.logging import get_logger
from . import merge_hooks, security, settings
from .models import (
    AuthAuditEvent,
    AuthLinkToken,
    AuthLoginAttempt,
    AuthSession,
    AuthUser,
    AuthUserEmail,
    now,
    utc,
)

log = get_logger(__name__)


@dataclasses.dataclass(frozen=True)
class Identity:
    """Who a valid session belongs to. Never sent to the client as a whole."""

    session_id: int
    user_id: int
    email: str
    is_admin: bool


class AdminActionError(Exception):
    """An admin action that is refused; the message is shown to the admin."""


# --------------------------------------------------------------------------
# Audit


def audit(
    db: Session,
    event: str,
    *,
    actor_user_id: int | None = None,
    subject_user_id: int | None = None,
    email: str | None = None,
    client_ip: str = "",
    detail: str = "",
) -> None:
    """Record a security event in the database and the structured log.

    Addresses are only ever stored and logged as a digest. The caller commits.
    """
    digest = security.email_hash(email) if email else ""
    db.add(
        AuthAuditEvent(
            event=event,
            actor_user_id=actor_user_id,
            subject_user_id=subject_user_id,
            email_hash=digest,
            client_ip=client_ip,
            detail=detail,
        )
    )
    log.info(
        event,
        actor_user_id=actor_user_id,
        subject_user_id=subject_user_id,
        email_hash=digest or None,
        client_ip=client_ip or None,
        detail=detail or None,
    )


# --------------------------------------------------------------------------
# Lookups


def _user_for_email(db: Session, email: str) -> AuthUser | None:
    row = db.exec(select(AuthUserEmail).where(AuthUserEmail.email == email)).first()
    return db.get(AuthUser, row.user_id) if row else None


def admin_user_id(db: Session) -> int | None:
    """The account that owns ``ADMIN_EMAIL``, once the admin has signed in."""
    if settings.ADMIN_EMAIL is None:
        return None
    user = _user_for_email(db, settings.ADMIN_EMAIL)
    return user.id if user else None


def _is_admin_account(db: Session, user_id: int) -> bool:
    return user_id == admin_user_id(db)


def _is_admin_address(db: Session, email: str, user: AuthUser | None) -> bool:
    """The admin signs in with a password only — no address of the admin
    account ever receives a magic link."""
    return email == settings.ADMIN_EMAIL or (
        user is not None and user.id is not None and _is_admin_account(db, user.id)
    )


def _create_session(
    db: Session,
    user: AuthUser,
    email: str,
    *,
    is_admin: bool,
    client_ip: str,
    user_agent: str,
) -> str:
    assert user.id is not None
    token = security.new_token()
    db.add(
        AuthSession(
            user_id=user.id,
            token_hash=security.token_hash(token),
            email=email,
            is_admin=is_admin,
            client_ip=client_ip,
            user_agent=user_agent[:300],
            expires_at=now() + settings.SESSION_EXPIRATION,
        )
    )
    user.last_login_at = now()
    db.add(user)
    return token


# --------------------------------------------------------------------------
# Magic links

LinkOutcome = Literal[
    "sent",
    "invalid_address",
    "domain_not_allowed",
    "admin_address",
    "blocked",
    "rate_limited",
]


def request_link(
    db: Session, raw_email: str, *, client_ip: str, redirect_to: str
) -> tuple[str | None, LinkOutcome]:
    """Issue a single-use link token, or say (for the audit log) why not.

    Returns the plaintext token only when one was issued; it is never stored.
    """
    email = security.normalize_email(raw_email)
    user = _user_for_email(db, email) if email else None
    outcome: LinkOutcome
    token: str | None = None
    if email is None:
        outcome = "invalid_address"
    elif not security.domain_allowed(email):
        outcome = "domain_not_allowed"
    elif _is_admin_address(db, email, user):
        outcome = "admin_address"
    elif user is not None and user.blocked_at is not None:
        outcome = "blocked"
    elif _recent_links(db, email=email) >= settings.LINK_RATE_LIMIT or (
        _recent_links(db, client_ip=client_ip) >= settings.LINK_RATE_LIMIT_PER_IP
    ):
        outcome = "rate_limited"
    else:
        # Only one live link per address: requesting a new one kills the old.
        db.exec(
            update(AuthLinkToken)
            .where(
                col(AuthLinkToken.email) == email,
                col(AuthLinkToken.used_at).is_(None),
                col(AuthLinkToken.expires_at) > now(),
            )
            .values(expires_at=now())
        )
        token = security.new_token()
        db.add(
            AuthLinkToken(
                email=email,
                token_hash=security.token_hash(token),
                redirect_to=redirect_to,
                client_ip=client_ip,
                expires_at=now() + settings.LINK_EXPIRATION,
            )
        )
        outcome = "sent"

    audit(
        db,
        "auth.link_requested",
        subject_user_id=user.id if user else None,
        email=email or raw_email,
        client_ip=client_ip,
        detail=outcome,
    )
    db.commit()
    return token, outcome


def _recent_links(db: Session, *, email: str | None = None, client_ip: str | None = None) -> int:
    since = now() - settings.LINK_EXPIRATION
    query = (
        select(func.count())
        .select_from(AuthLinkToken)
        .where(col(AuthLinkToken.created_at) >= since)
    )
    if email is not None:
        query = query.where(col(AuthLinkToken.email) == email)
    if client_ip is not None:
        query = query.where(col(AuthLinkToken.client_ip) == client_ip)
    return int(db.exec(query).one())


def peek_link(db: Session, token: str) -> bool:
    """Whether a link is still redeemable. Read-only: mail scanners that
    prefetch the link must not be able to use it up."""
    row = db.exec(
        select(AuthLinkToken).where(AuthLinkToken.token_hash == security.token_hash(token))
    ).first()
    return row is not None and row.used_at is None and utc(row.expires_at) > now()


def redeem_link(
    db: Session, token: str, *, client_ip: str, user_agent: str
) -> tuple[str, str] | None:
    """Spend a link token. Returns ``(session_token, redirect_to)`` or ``None``.

    The account is created here, on first successful sign-in — requesting a
    link never creates one. Domain, admin and block checks are repeated
    because they may have changed since the link was sent.
    """
    row = db.exec(
        select(AuthLinkToken).where(AuthLinkToken.token_hash == security.token_hash(token))
    ).first()
    if row is None or row.used_at is not None or utc(row.expires_at) <= now():
        audit(db, "auth.login_failed", client_ip=client_ip, detail="link_invalid")
        db.commit()
        return None

    # Atomic single use: two concurrent requests cannot both win this update.
    spent = db.exec(
        update(AuthLinkToken)
        .where(col(AuthLinkToken.id) == row.id, col(AuthLinkToken.used_at).is_(None))
        .values(used_at=now())
    )
    if spent.rowcount != 1:
        db.rollback()
        return None

    email = row.email
    user = _user_for_email(db, email)
    refused: str | None = None
    if not security.domain_allowed(email):
        refused = "domain_not_allowed"
    elif _is_admin_address(db, email, user):
        refused = "admin_address"
    elif user is not None and user.blocked_at is not None:
        refused = "blocked"
    if refused:
        audit(db, "auth.login_failed", email=email, client_ip=client_ip, detail=refused)
        db.commit()
        return None

    if user is None:
        user = AuthUser()
        db.add(user)
        db.flush()
        assert user.id is not None
        db.add(AuthUserEmail(user_id=user.id, email=email))
        audit(db, "auth.account_created", subject_user_id=user.id, email=email, client_ip=client_ip)

    session_token = _create_session(
        db, user, email, is_admin=False, client_ip=client_ip, user_agent=user_agent
    )
    audit(db, "auth.login", subject_user_id=user.id, client_ip=client_ip, detail="magic_link")
    db.commit()
    return session_token, row.redirect_to


# --------------------------------------------------------------------------
# Admin password login

AdminOutcome = Literal["ok", "invalid", "locked", "disabled"]


def admin_login(
    db: Session, raw_email: str, password: str, *, client_ip: str, user_agent: str
) -> tuple[str | None, AdminOutcome]:
    if settings.ADMIN_EMAIL is None or settings.ADMIN_PASSWORD_HASH is None:
        return None, "disabled"

    since = now() - settings.ADMIN_LOCKOUT
    failures = (
        select(func.count())
        .select_from(AuthLoginAttempt)
        .where(col(AuthLoginAttempt.created_at) >= since, col(AuthLoginAttempt.success).is_(False))
    )
    per_ip = int(db.exec(failures.where(col(AuthLoginAttempt.client_ip) == client_ip)).one())
    overall = int(db.exec(failures).one())
    if (
        per_ip >= settings.ADMIN_MAX_FAILURES_PER_IP
        or overall >= settings.ADMIN_MAX_FAILURES_GLOBAL
    ):
        audit(db, "auth.admin_locked", client_ip=client_ip, detail=f"ip={per_ip} global={overall}")
        db.commit()
        return None, "locked"

    email = security.normalize_email(raw_email)
    if email == settings.ADMIN_EMAIL:
        ok = security.verify_password(password, settings.ADMIN_PASSWORD_HASH)
    else:
        security.verify_password(password, security.dummy_password_hash())
        ok = False

    db.add(AuthLoginAttempt(client_ip=client_ip, success=ok))
    if not ok:
        audit(
            db, "auth.login_failed", email=raw_email, client_ip=client_ip, detail="admin_password"
        )
        db.commit()
        return None, "invalid"

    assert email is not None
    user = _user_for_email(db, email)
    if user is None:
        user = AuthUser()
        db.add(user)
        db.flush()
        assert user.id is not None
        db.add(AuthUserEmail(user_id=user.id, email=email))
    token = _create_session(
        db, user, email, is_admin=True, client_ip=client_ip, user_agent=user_agent
    )
    audit(db, "auth.login", subject_user_id=user.id, client_ip=client_ip, detail="admin_password")
    db.commit()
    return token, "ok"


# --------------------------------------------------------------------------
# Sessions


def resolve_session(db: Session, token_hash: str) -> Identity | None:
    """The identity behind a session-token digest, if the session is live and
    its account is not blocked."""
    if not token_hash:
        return None
    row = db.exec(select(AuthSession).where(AuthSession.token_hash == token_hash)).first()
    if row is None or row.id is None or row.revoked_at is not None or utc(row.expires_at) <= now():
        return None
    user = db.get(AuthUser, row.user_id)
    if user is None or user.blocked_at is not None:
        return None
    return Identity(session_id=row.id, user_id=row.user_id, email=row.email, is_admin=row.is_admin)


def _revoke_where(db: Session, *conditions: ColumnElement[bool]) -> int:
    result = db.exec(
        update(AuthSession)
        .where(col(AuthSession.revoked_at).is_(None), *conditions)
        .values(revoked_at=now())
    )
    return int(result.rowcount)


def logout(db: Session, token_hash: str, *, everywhere: bool, client_ip: str) -> None:
    identity = resolve_session(db, token_hash)
    if identity is None:
        return
    if everywhere:
        count = _revoke_where(db, col(AuthSession.user_id) == identity.user_id)
    else:
        count = _revoke_where(db, col(AuthSession.id) == identity.session_id)
    audit(
        db,
        "auth.logout_everywhere" if everywhere else "auth.logout",
        actor_user_id=identity.user_id,
        subject_user_id=identity.user_id,
        client_ip=client_ip,
        detail=f"sessions={count}",
    )
    db.commit()


# --------------------------------------------------------------------------
# Admin actions. Authorization is enforced by ``auth=is_admin`` on the event
# handlers that call these; the checks below protect the data, not the caller.


def revoke_session(db: Session, session_id: int, *, actor_user_id: int) -> None:
    row = db.get(AuthSession, session_id)
    if row is None:
        raise AdminActionError("That session no longer exists.")
    _revoke_where(db, col(AuthSession.id) == session_id)
    audit(
        db,
        "admin.session_revoked",
        actor_user_id=actor_user_id,
        subject_user_id=row.user_id,
        detail=f"session={session_id}",
    )
    db.commit()


def set_blocked(db: Session, user_id: int, blocked: bool, *, actor_user_id: int) -> None:
    user = db.get(AuthUser, user_id)
    if user is None:
        raise AdminActionError("That account no longer exists.")
    if _is_admin_account(db, user_id):
        raise AdminActionError("The admin account cannot be blocked.")
    user.blocked_at = now() if blocked else None
    db.add(user)
    count = _revoke_where(db, col(AuthSession.user_id) == user_id) if blocked else 0
    audit(
        db,
        "admin.user_blocked" if blocked else "admin.user_unblocked",
        actor_user_id=actor_user_id,
        subject_user_id=user_id,
        detail=f"sessions={count}" if blocked else "",
    )
    db.commit()


def merge_users(db: Session, source_id: int, target_id: int, *, actor_user_id: int) -> None:
    """Fold ``source`` into ``target``: its addresses move over, app data is
    re-pointed by ``merge_hooks``, every session of both accounts ends, and the
    source account is deleted. All in one transaction."""
    if source_id == target_id:
        raise AdminActionError("Pick two different accounts.")
    source, target = db.get(AuthUser, source_id), db.get(AuthUser, target_id)
    if source is None or target is None:
        raise AdminActionError("One of the accounts no longer exists.")
    if _is_admin_account(db, source_id) or _is_admin_account(db, target_id):
        raise AdminActionError("The admin account cannot be merged.")
    if source.blocked_at is not None or target.blocked_at is not None:
        raise AdminActionError("Unblock both accounts before merging them.")

    moved = list(db.exec(select(AuthUserEmail).where(AuthUserEmail.user_id == source_id)).all())
    for row in moved:
        row.user_id = target_id
        db.add(row)
    revoked = _revoke_where(db, col(AuthSession.user_id).in_([source_id, target_id]))
    # Sessions keep their history but now point at the surviving account.
    db.exec(
        update(AuthSession).where(col(AuthSession.user_id) == source_id).values(user_id=target_id)
    )
    for hook in merge_hooks.MERGE_HOOKS:
        hook(db, source_id, target_id)
    db.flush()
    db.delete(source)
    audit(
        db,
        "admin.users_merged",
        actor_user_id=actor_user_id,
        subject_user_id=target_id,
        detail=f"source={source_id} emails={len(moved)} sessions={revoked}",
    )
    db.commit()


# --------------------------------------------------------------------------
# Housekeeping


def purge_expired(db: Session, older_than: timedelta) -> dict[str, int]:
    """Delete auth rows that can no longer matter, once they are older than
    ``older_than``: spent or expired links, ended or expired sessions, and
    admin login attempts (the lockout window is far shorter). The audit log
    and accounts are never touched. Returns the deleted counts per table."""
    cutoff = now() - older_than
    results = {
        "links": db.exec(
            delete(AuthLinkToken).where(
                col(AuthLinkToken.created_at) < cutoff,
                or_(col(AuthLinkToken.used_at).is_not(None), col(AuthLinkToken.expires_at) < now()),
            )
        ),
        "sessions": db.exec(
            delete(AuthSession).where(
                or_(col(AuthSession.revoked_at) < cutoff, col(AuthSession.expires_at) < cutoff)
            )
        ),
        "login_attempts": db.exec(
            delete(AuthLoginAttempt).where(col(AuthLoginAttempt.created_at) < cutoff)
        ),
    }
    db.commit()
    counts = {name: int(result.rowcount) for name, result in results.items()}
    log.info("auth.purge", **counts)
    return counts


# --------------------------------------------------------------------------
# Admin listings


@dataclasses.dataclass(frozen=True)
class UserRow:
    id: int
    emails: str
    created_at: str
    last_login_at: str
    blocked: bool
    active_sessions: int
    is_admin: bool


@dataclasses.dataclass(frozen=True)
class SessionRow:
    id: int
    user_id: int
    email: str
    is_admin: bool
    client_ip: str
    user_agent: str
    created_at: str
    expires_at: str


@dataclasses.dataclass(frozen=True)
class AuditRow:
    id: int
    created_at: str
    event: str
    actor: str
    subject: str
    client_ip: str
    detail: str


def _fmt(value: datetime | None) -> str:
    return utc(value).strftime("%Y-%m-%d %H:%M UTC") if value else "—"


def _emails_by_user(db: Session) -> dict[int, list[str]]:
    out: dict[int, list[str]] = {}
    for row in db.exec(select(AuthUserEmail).order_by(col(AuthUserEmail.email))).all():
        out.setdefault(row.user_id, []).append(row.email)
    return out


def _live_session_filter() -> list[ColumnElement[bool]]:
    return [col(AuthSession.revoked_at).is_(None), col(AuthSession.expires_at) > now()]


def list_users(db: Session) -> list[UserRow]:
    emails = _emails_by_user(db)
    admin_id = admin_user_id(db)
    counts = dict(
        db.exec(
            select(AuthSession.user_id, func.count())
            .where(*_live_session_filter())
            .group_by(col(AuthSession.user_id))
        ).all()
    )
    return [
        UserRow(
            id=u.id,
            emails=", ".join(emails.get(u.id, [])),
            created_at=_fmt(u.created_at),
            last_login_at=_fmt(u.last_login_at),
            blocked=u.blocked_at is not None,
            active_sessions=int(counts.get(u.id, 0)),
            is_admin=u.id == admin_id,
        )
        for u in db.exec(select(AuthUser).order_by(col(AuthUser.id))).all()
        if u.id is not None
    ]


def list_sessions(db: Session) -> list[SessionRow]:
    rows = db.exec(
        select(AuthSession)
        .where(*_live_session_filter())
        .order_by(col(AuthSession.created_at).desc())
    ).all()
    return [
        SessionRow(
            id=s.id,
            user_id=s.user_id,
            email=s.email,
            is_admin=s.is_admin,
            client_ip=s.client_ip,
            user_agent=s.user_agent,
            created_at=_fmt(s.created_at),
            expires_at=_fmt(s.expires_at),
        )
        for s in rows
        if s.id is not None
    ]


def list_audit(db: Session, limit: int = 200) -> list[AuditRow]:
    emails = _emails_by_user(db)

    def who(user_id: int | None) -> str:
        if user_id is None:
            return "—"
        return ", ".join(emails.get(user_id, [])) or f"#{user_id} (deleted)"

    rows = db.exec(
        select(AuthAuditEvent).order_by(col(AuthAuditEvent.id).desc()).limit(limit)
    ).all()
    return [
        AuditRow(
            id=r.id,
            created_at=_fmt(r.created_at),
            event=r.event,
            actor=who(r.actor_user_id),
            subject=who(r.subject_user_id)
            if r.subject_user_id
            else (f"hash {r.email_hash}" if r.email_hash else "—"),
            client_ip=r.client_ip or "—",
            detail=r.detail,
        )
        for r in rows
        if r.id is not None
    ]
