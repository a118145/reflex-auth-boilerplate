"""Domain rules: who may do what. The gate every caller goes through.

Plain functions over a ``Session``, each taking the acting user's id and
checking what that user may see or do. The UI declares the same rules with
``auth=`` checks (``auth/policy.py``) — those decide what a handler may be
called for; this package enforces the rules again, so that no other caller
(a script, an API, a second process) can bypass them.

One module per area; everything public is re-exported here, so callers write
``from .. import service`` and ``service.create_group(...)``. The exception
is ``sharing``, used by its own name
(``service.sharing.share_with_user(db, service.sharing.NOTES, ...)``): its
functions are generic over what is shared.

* ``errors``  — how the service refuses; messages are written for the user
* ``models``  — the tables the service owns (groups) and the person columns
* ``wire``    — plain values that cross to a user interface, never table rows
* ``sharing`` — one owner; shared with a person, a group, or everyone
* ``groups``  — named sets of people, managed by the admin
* ``views``   — what a screen shows, read in one checked call
* ``people``  — what happens to a person's data on merge and on delete

The package never imports ``reflex`` or the app's UI: it is the backend
contract. ``tests/test_service_layout.py`` pins the layout.
"""

from . import sharing
from .errors import DomainError, PermissionDeniedError
from .groups import (
    add_member,
    create_group,
    delete_group,
    group_members,
    groups_of_user,
    list_groups,
    remove_member,
    rename_group,
)
from .models import (
    GRANTEE_COLUMNS,
    OWNER_COLUMNS,
    TABLES,
    GroupMember,
    PersonColumn,
    UserGroup,
    utcnow,
)
from .people import (
    grantee_columns,
    hand_over_person,
    merge_people,
    owner_columns,
)
from .views import group_list, group_rows
from .wire import GroupInfo, GroupRow, group_info

__all__ = [
    "GRANTEE_COLUMNS",
    "OWNER_COLUMNS",
    "TABLES",
    "DomainError",
    "GroupInfo",
    "GroupMember",
    "GroupRow",
    "PermissionDeniedError",
    "PersonColumn",
    "UserGroup",
    "add_member",
    "create_group",
    "delete_group",
    "grantee_columns",
    "group_info",
    "group_list",
    "group_members",
    "group_rows",
    "groups_of_user",
    "hand_over_person",
    "list_groups",
    "merge_people",
    "owner_columns",
    "remove_member",
    "rename_group",
    "sharing",
    "utcnow",
]
