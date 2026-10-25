"""Re-point app data when the admin merges two accounts.

Every app table that belongs to a person must reference ``authuser.id`` and
get a hook here. A merge moves the source account's addresses to the target
and then **deletes the source account**; a table without a hook is left
pointing at an id that no longer exists.

Hooks run inside the merge transaction, before the source row is deleted. Do
not commit in a hook. Raise to abort the whole merge.

Example, for a table ``Note`` with a ``user_id`` column::

    from sqlalchemy import update
    from sqlmodel import Session, col

    from ..models import Note


    def _move_notes(db: Session, source_id: int, target_id: int) -> None:
        db.exec(update(Note).where(col(Note.user_id) == source_id).values(user_id=target_id))


    MERGE_HOOKS: list[MergeHook] = [_move_notes]
"""

from collections.abc import Callable

from sqlmodel import Session

MergeHook = Callable[[Session, int, int], None]

MERGE_HOOKS: list[MergeHook] = []
