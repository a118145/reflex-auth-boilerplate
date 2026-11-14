"""Sharing, written once.

A shareable thing has one owner. Others read it when it is shared with
everyone, with them, or with a group they are in. Only the owner shares, and
only the owner sees who else has access. There is no admin bypass: the admin
manages accounts and groups, not other people's data.

What can be shared is described by a ``Shareable``; every function here takes
one. Rules that belong to one kind only (archived things drop out of other
people's lists, say) stay with that kind and build on ``readable``.

**A new shareable kind** is a model with an owner column and a
``shared_with_all: bool`` column, two share tables, one ``Shareable`` in
``KINDS`` below, and one ``load_*`` handler in ``states/share_state.py`` —
never a copy of these functions. ``references/ownership_and_sharing.md`` of
the skill that generated this file walks through it; the short form::

    class Note(SQLModel, table=True):
        id: int | None = Field(default=None, primary_key=True)
        owner_id: int = Field(foreign_key="authuser.id", index=True)
        shared_with_all: bool = False
        ...

    class NoteShare(SQLModel, table=True):
        __table_args__ = (UniqueConstraint("note_id", "user_id"),)
        id: int | None = Field(default=None, primary_key=True)
        note_id: int = Field(foreign_key="note.id", index=True)
        user_id: int = Field(foreign_key="authuser.id", index=True)

    class NoteGroupShare(SQLModel, table=True):
        __table_args__ = (UniqueConstraint("note_id", "group_id"),)
        id: int | None = Field(default=None, primary_key=True)
        note_id: int = Field(foreign_key="note.id", index=True)
        group_id: int = Field(foreign_key="usergroup.id", index=True)

    NOTES = Shareable(
        kind="note", owner_word="owner", model=Note, owner_column="owner_id",
        user_share=NoteShare, group_share=NoteGroupShare, target_column="note_id",
    )
    KINDS = (NOTES,)
"""

from dataclasses import dataclass
from typing import Any

from sqlalchemy import ColumnElement, delete, update
from sqlmodel import Session, SQLModel, col, or_, select

from .errors import DomainError, PermissionDeniedError
from .models import GroupMember, UserGroup


@dataclass(frozen=True)
class Shareable[M: SQLModel]:
    """One kind of thing that can be shared, and where its shares are kept."""

    kind: str  # in messages and log events: "note"
    owner_word: str  # in messages: "owner", "author", "uploader"
    model: type[M]  # has ``id``, the owner column and ``shared_with_all``
    owner_column: str
    user_share: type[SQLModel]  # rows of (target column, ``user_id``)
    group_share: type[SQLModel]  # rows of (target column, ``group_id``)
    target_column: str  # the share tables' column pointing at ``model.id``


# Declare the app's shareable kinds here, importing their models above.
KINDS: tuple[Shareable[Any], ...] = ()


def _column(model: type[SQLModel], name: str) -> Any:
    """A mapped column by name — the one place this module leaves the types."""
    return getattr(model, name)


def _target(what: Shareable[Any], share: type[SQLModel]) -> Any:
    return _column(share, what.target_column)


# --------------------------------------------------------------------------
# Reading


def readable[M: SQLModel](what: Shareable[M], user_id: int) -> ColumnElement[bool]:
    """SQL predicate over ``what.model``: the rows ``user_id`` may read.

    Every list of a shareable kind is ``select(Model).where(readable(...))``
    — never a bare ``select(Model)``.
    """
    direct = select(_target(what, what.user_share)).where(
        _column(what.user_share, "user_id") == user_id
    )
    via_group = (
        select(_target(what, what.group_share))
        .join(GroupMember, col(GroupMember.group_id) == _column(what.group_share, "group_id"))
        .where(GroupMember.user_id == user_id)
    )
    ident = _column(what.model, "id")
    return or_(
        _column(what.model, what.owner_column) == user_id,
        _column(what.model, "shared_with_all"),
        ident.in_(direct),
        ident.in_(via_group),
    )


def can_view[M: SQLModel](db: Session, what: Shareable[M], user_id: int, item: M) -> bool:
    if getattr(item, what.owner_column) == user_id or getattr(item, "shared_with_all"):  # noqa: B009
        return True
    ident = _column(what.model, "id")
    query = select(ident).where(ident == getattr(item, "id"), readable(what, user_id))  # noqa: B009
    return db.exec(query).first() is not None


def get_viewable[M: SQLModel](db: Session, what: Shareable[M], user_id: int, target_id: int) -> M:
    item = db.get(what.model, target_id)
    if item is None or not can_view(db, what, user_id, item):
        # Same answer for "missing" and "not yours": existence is not leaked.
        raise PermissionDeniedError(f"This {what.kind} does not exist or is not shared with you.")
    return item


def owned[M: SQLModel](db: Session, what: Shareable[M], actor: int, target_id: int) -> M:
    item = db.get(what.model, target_id)
    if item is None or getattr(item, what.owner_column) != actor:
        raise PermissionDeniedError(f"Only the {what.owner_word} may change this {what.kind}.")
    return item


def user_shares_of(db: Session, what: Shareable[Any], target_id: int) -> list[int]:
    """The people it is shared with directly."""
    query = select(_column(what.user_share, "user_id")).where(
        _target(what, what.user_share) == target_id
    )
    return list(db.exec(query).all())


def group_shares_of(db: Session, what: Shareable[Any], target_id: int) -> list[int]:
    """The groups it is shared with."""
    query = select(_column(what.group_share, "group_id")).where(
        _target(what, what.group_share) == target_id
    )
    return list(db.exec(query).all())


@dataclass(frozen=True)
class Shares:
    """Who a thing is shared with, as its owner sees it."""

    shared_with_all: bool
    users: list[int]
    groups: list[int]


def shares_of(db: Session, what: Shareable[Any], actor: int, target_id: int) -> Shares:
    """Only the owner sees who else has access."""
    item = owned(db, what, actor, target_id)
    return Shares(
        shared_with_all=bool(getattr(item, "shared_with_all")),  # noqa: B009
        users=user_shares_of(db, what, target_id),
        groups=group_shares_of(db, what, target_id),
    )


def shared_with_user(db: Session, what: Shareable[Any], user_id: int) -> list[int]:
    """Ids of the things shared with this person directly."""
    query = select(_target(what, what.user_share)).where(
        _column(what.user_share, "user_id") == user_id
    )
    return list(db.exec(query).all())


# --------------------------------------------------------------------------
# The owner shares


def share_with_user(
    db: Session, what: Shareable[Any], actor: int, target_id: int, user_id: int
) -> None:
    owned(db, what, actor, target_id)
    if user_id == actor:
        raise DomainError(f"The {what.owner_word} already has the {what.kind}.")
    if user_id in user_shares_of(db, what, target_id):
        return
    db.add(what.user_share(**{what.target_column: target_id, "user_id": user_id}))
    db.commit()


def unshare_user(
    db: Session, what: Shareable[Any], actor: int, target_id: int, user_id: int
) -> None:
    owned(db, what, actor, target_id)
    db.exec(
        delete(what.user_share).where(
            _target(what, what.user_share) == target_id,
            _column(what.user_share, "user_id") == user_id,
        )
    )
    db.commit()


def share_with_group(
    db: Session, what: Shareable[Any], actor: int, target_id: int, group_id: int
) -> None:
    """Every member, present and future, may read it."""
    owned(db, what, actor, target_id)
    if db.get(UserGroup, group_id) is None:
        raise DomainError("This group does not exist.")
    if group_id in group_shares_of(db, what, target_id):
        return
    db.add(what.group_share(**{what.target_column: target_id, "group_id": group_id}))
    db.commit()


def unshare_group(
    db: Session, what: Shareable[Any], actor: int, target_id: int, group_id: int
) -> None:
    owned(db, what, actor, target_id)
    db.exec(
        delete(what.group_share).where(
            _target(what, what.group_share) == target_id,
            _column(what.group_share, "group_id") == group_id,
        )
    )
    db.commit()


def set_shared_with_all(
    db: Session, what: Shareable[Any], actor: int, target_id: int, shared: bool
) -> None:
    item = owned(db, what, actor, target_id)
    setattr(item, "shared_with_all", shared)  # noqa: B010
    db.add(item)
    db.commit()


# --------------------------------------------------------------------------
# When the thing itself, a group or an account goes (``groups``, ``people``,
# the kind's own delete). No commit: these run inside the caller's
# transaction.


def drop_shares_of(db: Session, what: Shareable[Any], target_id: int) -> None:
    """Before the shared thing is deleted: its shares go first."""
    for share in (what.user_share, what.group_share):
        db.exec(delete(share).where(_target(what, share) == target_id))


def drop_group_shares(db: Session, group_id: int) -> None:
    """Before a group is deleted: nothing stays shared with it."""
    for what in KINDS:
        db.exec(
            delete(what.group_share).where(_column(what.group_share, "group_id") == group_id)
        )


def repoint_user_shares(db: Session, what: Shareable[Any], source_id: int, target_id: int) -> None:
    """Shares of ``source_id`` become ``target_id``'s — never two for one
    person: where the target already has one, the source's is dropped."""
    user = _column(what.user_share, "user_id")
    target = _target(what, what.user_share)
    already = set(shared_with_user(db, what, target_id))
    db.exec(delete(what.user_share).where(user == source_id, target.in_(already)))
    db.flush()
    db.exec(update(what.user_share).where(user == source_id).values(user_id=target_id))


def drop_user_shares(db: Session, what: Shareable[Any], user_id: int) -> None:
    """Access granted to a person who is being deleted is not inherited."""
    db.exec(delete(what.user_share).where(_column(what.user_share, "user_id") == user_id))


def drop_shares_with_owner(db: Session, what: Shareable[Any], owner_id: int) -> None:
    """Never a share for the owner of the thing shared."""
    own = select(_column(what.model, "id")).where(
        _column(what.model, what.owner_column) == owner_id
    )
    db.exec(
        delete(what.user_share).where(
            _column(what.user_share, "user_id") == owner_id,
            _target(what, what.user_share).in_(own),
        )
    )
