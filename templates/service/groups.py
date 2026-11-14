"""User groups: named sets of people, to share with.

Managing them is the admin's job. Being the admin is a property of the
session, which this package does not know — so the *app* enforces it
(``auth.authz.is_admin`` on every handler of the admin area), and these
functions take the actor only to record who did it. Names are visible to
everyone, members only to the admin.
"""

from sqlalchemy import delete, func
from sqlmodel import Session, col, select

from . import sharing
from .errors import DomainError
from .models import GroupMember, UserGroup


def list_groups(db: Session) -> list[UserGroup]:
    return list(db.exec(select(UserGroup).order_by(col(UserGroup.name))).all())


def group_members(db: Session, group_id: int) -> list[int]:
    return list(db.exec(select(GroupMember.user_id).where(GroupMember.group_id == group_id)).all())


def member_counts(db: Session) -> dict[int, int]:
    rows = db.exec(
        select(GroupMember.group_id, func.count()).group_by(col(GroupMember.group_id))
    ).all()
    return {group_id: count for group_id, count in rows}


def groups_of_user(db: Session, user_id: int) -> list[int]:
    return list(db.exec(select(GroupMember.group_id).where(GroupMember.user_id == user_id)).all())


def _existing(db: Session, group_id: int) -> UserGroup:
    group = db.get(UserGroup, group_id)
    if group is None:
        raise DomainError("This group does not exist.")
    return group


def _free_group_name(db: Session, name: str, group_id: int | None = None) -> str:
    name = name.strip()
    if not name:
        raise DomainError("Name is missing.")
    other = db.exec(select(UserGroup.id).where(UserGroup.name == name)).first()
    if other is not None and other != group_id:
        raise DomainError(f'A group named "{name}" already exists.')
    return name


def create_group(db: Session, actor: int, name: str) -> UserGroup:
    group = UserGroup(name=_free_group_name(db, name), created_by=actor)
    db.add(group)
    db.commit()
    db.refresh(group)
    return group


def rename_group(db: Session, actor: int, group_id: int, name: str) -> None:
    group = _existing(db, group_id)
    group.name = _free_group_name(db, name, group_id)
    db.add(group)
    db.commit()


def delete_group(db: Session, actor: int, group_id: int) -> None:
    """Members and shares go with it; what was shared stays."""
    _existing(db, group_id)
    sharing.drop_group_shares(db, group_id)
    db.exec(delete(GroupMember).where(col(GroupMember.group_id) == group_id))
    db.exec(delete(UserGroup).where(col(UserGroup.id) == group_id))
    db.commit()


def add_member(db: Session, actor: int, group_id: int, user_id: int) -> None:
    _existing(db, group_id)
    if user_id in group_members(db, group_id):
        return
    db.add(GroupMember(group_id=group_id, user_id=user_id))
    db.commit()


def remove_member(db: Session, actor: int, group_id: int, user_id: int) -> None:
    db.exec(
        delete(GroupMember).where(
            col(GroupMember.group_id) == group_id, col(GroupMember.user_id) == user_id
        )
    )
    db.commit()
