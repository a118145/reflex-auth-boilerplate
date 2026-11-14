"""What happens to a person's data when accounts are merged or deleted.

Called through ``auth/merge_hooks.py``, inside the admin's transaction: no
commit here, and raising aborts the whole merge or delete.

* **Merge** (one person, two accounts): everything of the source becomes the
  target's. Where a grant may exist only once — a membership per group, a
  share per thing — the source's duplicate is dropped first.
* **Delete**: what the person owns is handed over to another account; access
  granted to the person is dropped, not inherited.

Which columns hold a person is declared in ``models`` (``OWNER_COLUMNS``,
``GRANTEE_COLUMNS``) and by each ``Shareable`` in ``sharing.KINDS``.
"""

from sqlalchemy import delete, update
from sqlmodel import Session, col, select

from . import sharing
from .errors import DomainError
from .models import GRANTEE_COLUMNS, OWNER_COLUMNS, GroupMember, PersonColumn


def owner_columns() -> list[PersonColumn]:
    """Every column holding what a person made or owns."""
    return [*OWNER_COLUMNS, *((what.model, what.owner_column) for what in sharing.KINDS)]


def grantee_columns() -> list[PersonColumn]:
    """Every column holding access granted to a person."""
    return [
        (GroupMember, "user_id"),
        *((what.user_share, "user_id") for what in sharing.KINDS),
        *GRANTEE_COLUMNS,
    ]


def _repoint(db: Session, columns: list[PersonColumn], source_id: int, target_id: int) -> None:
    for model, column in columns:
        db.exec(
            update(model).where(getattr(model, column) == source_id).values({column: target_id})
        )


def merge_people(db: Session, source_id: int, target_id: int) -> None:
    """Re-point everything of ``source_id`` to ``target_id``."""
    # One membership per group: drop the source's where the target is a member.
    target_groups = db.exec(
        select(GroupMember.group_id).where(GroupMember.user_id == target_id)
    ).all()
    db.exec(
        delete(GroupMember).where(
            col(GroupMember.user_id) == source_id, col(GroupMember.group_id).in_(target_groups)
        )
    )
    # Likewise one share per shared thing.
    for what in sharing.KINDS:
        sharing.repoint_user_shares(db, what, source_id, target_id)
    db.flush()
    _repoint(db, [*owner_columns(), (GroupMember, "user_id"), *GRANTEE_COLUMNS], source_id, target_id)
    # ... and never a share for the owner of the thing shared.
    _drop_shares_with_owner(db, target_id)


def hand_over_person(db: Session, source_id: int, target_id: int) -> None:
    """Before ``source_id`` is deleted: what they own goes to ``target_id``,
    access granted to them is dropped."""
    if source_id == target_id:
        raise DomainError("Hand the data over to another person.")
    for model, column in grantee_columns():
        db.exec(delete(model).where(getattr(model, column) == source_id))
    db.flush()
    _repoint(db, owner_columns(), source_id, target_id)
    _drop_shares_with_owner(db, target_id)


def _drop_shares_with_owner(db: Session, owner_id: int) -> None:
    for what in sharing.KINDS:
        sharing.drop_shares_with_owner(db, what, owner_id)
