"""The tables the service owns, and which columns hold a person.

Plain ``SQLModel`` tables without a Reflex import; the app module registers
``TABLES`` with Reflex so ``reflex db makemigrations`` sees them.

**A person is an ``authuser.id``** — never an e-mail address: addresses
change and accounts are merged. Every column that holds one is a foreign key
to ``authuser.id`` and is listed in exactly one of ``OWNER_COLUMNS`` and
``GRANTEE_COLUMNS`` (or belongs to a ``Shareable``, which lists it by
itself). ``tests/test_people.py`` fails for a column that is in neither.

Datetimes are timezone-aware UTC; sqlmodel >= 0.0.48 rejects naive values.
"""

from datetime import UTC, datetime

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel

PERSON = "authuser.id"


def utcnow() -> datetime:
    return datetime.now(UTC)


class UserGroup(SQLModel, table=True):
    """A named set of people, managed by the admin. Names are visible to
    everyone (to share with), members only to the admin."""

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(unique=True)
    created_by: int = Field(foreign_key=PERSON)
    created_at: datetime = Field(default_factory=utcnow)


class GroupMember(SQLModel, table=True):
    """A person may be in several groups, in each once."""

    __table_args__ = (UniqueConstraint("group_id", "user_id"),)

    id: int | None = Field(default=None, primary_key=True)
    group_id: int = Field(foreign_key="usergroup.id", index=True)
    user_id: int = Field(foreign_key=PERSON, index=True)
    created_at: datetime = Field(default_factory=utcnow)


TABLES: tuple[type[SQLModel], ...] = (UserGroup, GroupMember)

PersonColumn = tuple[type[SQLModel], str]

OWNER_COLUMNS: list[PersonColumn] = [
    (UserGroup, "created_by"),
]
"""What a person made or owns. A merge re-points these rows to the surviving
account; deleting the person hands them over to another. Add every app table
with an owner here — unless it is a ``Shareable``: its owner column is taken
from there."""

GRANTEE_COLUMNS: list[PersonColumn] = []
"""Access granted to a person. Deleting the person deletes these rows — the
new owner must not silently gain access. A merge re-points them; if the
table allows a grant only once per thing (a unique constraint), drop the
rows that would then exist twice first, as ``people.merge_people`` does for
group memberships. Shares and memberships are handled already; list here
only grants of your own making."""
