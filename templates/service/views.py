"""What a screen shows, read in one checked call.

One function per screen or panel, named for what the screen shows. Each
takes the acting user's id (unless what it returns is visible to every
signed-in user), checks access itself, and returns plain values from
``wire`` — so who may see what is decided here, not wherever a query happened
to be written. "Missing" and "not yours" give the same refusal.

Add the app's read models here, e.g.::

    def note_list(db: Session, me: int) -> list[NoteInfo]:
        rows = db.exec(select(Note).where(sharing.readable(sharing.NOTES, me))).all()
        return [note_info(n, mine=n.owner_id == me) for n in rows]
"""

from sqlmodel import Session

from .groups import list_groups, member_counts
from .wire import GroupInfo, GroupRow, group_info


def group_list(db: Session) -> list[GroupInfo]:
    """Group names are visible to everyone (to share with); members are not."""
    return [group_info(g) for g in list_groups(db)]


def group_rows(db: Session) -> list[GroupRow]:
    """The admin's list: every group with its member count. The app gates it
    with ``is_admin`` — see ``groups``."""
    counts = member_counts(db)
    return [
        GroupRow(id=g.id, name=g.name, members=counts.get(g.id, 0))
        for g in list_groups(db)
        if g.id is not None
    ]
