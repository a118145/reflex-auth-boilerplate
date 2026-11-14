"""What crosses from the service to a user interface: plain values.

The read models in ``views`` are built from these. Nothing here is a table
row: every field is a number, a string, a flag, a time, or a list or dict of
those, so a value can be turned into JSON as it is — which is what a backend
behind HTTP would send, and what any other client would be written against.
A field appears here because a screen needs it, not because the table has
it: adding a column to a table changes nothing a client sees until it is
added here on purpose.
"""

from dataclasses import dataclass

from .models import UserGroup


@dataclass(frozen=True)
class GroupInfo:
    id: int
    name: str


def group_info(g: UserGroup) -> GroupInfo:
    return GroupInfo(id=g.id or 0, name=g.name)


@dataclass(frozen=True)
class GroupRow:
    """A group as the admin lists it."""

    id: int
    name: str
    members: int
