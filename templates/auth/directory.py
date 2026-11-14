"""People by id and by address — the auth tables, read for display.

People are shown by their first e-mail address and found by any of them.
The service knows people only as ids, so these lookups live with the auth
tables; states run them through ``call``.
"""

from collections.abc import Iterable

from sqlmodel import Session, col, select

from .models import AuthUserEmail
from .security import normalize_email


def emails_for(db: Session, user_ids: Iterable[int | None]) -> dict[int, str]:
    ids = {i for i in user_ids if i is not None}
    if not ids:
        return {}
    rows = db.exec(
        select(AuthUserEmail)
        .where(col(AuthUserEmail.user_id).in_(ids))
        .order_by(col(AuthUserEmail.id))
    ).all()
    out: dict[int, str] = {}
    for row in rows:
        out.setdefault(row.user_id, row.email)
    return out


def user_by_email(db: Session, raw: str) -> int | None:
    email = normalize_email(raw)
    if email is None:
        return None
    row = db.exec(select(AuthUserEmail).where(AuthUserEmail.email == email)).first()
    return row.user_id if row else None
