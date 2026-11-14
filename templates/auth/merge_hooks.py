"""What the admin's merge and delete do to app data.

A merge moves the source account's addresses to the target and then
**deletes the source account**; a delete hands the account's data to another
and deletes it. A person column that no hook covers is left pointing at an
id that no longer exists.

The hooks are the service's: ``service/people.py`` re-points or drops every
column declared in ``service/models.py`` (``OWNER_COLUMNS``,
``GRANTEE_COLUMNS``) and by the shareable kinds. Declare a new table's
person column there — a hook of your own is needed only for what a column
list cannot express (names unique per owner that clash on a merge, say).

Hooks run inside the admin's transaction, before the account row is deleted.
Do not commit in a hook. Raise to abort the whole operation.
"""

from collections.abc import Callable

from sqlmodel import Session

from ..service import hand_over_person, merge_people

MergeHook = Callable[[Session, int, int], None]

# (db, source_id, target_id): everything of the source becomes the target's.
MERGE_HOOKS: list[MergeHook] = [merge_people]

# Deleting an account, same contract: owned rows move, granted access is dropped.
HAND_OVER_HOOKS: list[MergeHook] = [hand_over_person]
