# Making app data multi-user: ownership and sharing

After Step 5 of the skill everyone must sign in, but the app's own data is
still one shared pot: any signed-in user reads and changes every row. This
recipe turns a table into something a person **owns** and can **share** —
with a person, a group, or everyone.

It was applied to the scaffold's `Item` CRUD and verified end to end (gate
green; two browsers: the owner creates and shares, the other person sees
nothing before, reads after, gets no edit controls and no share card).
`Item` is the running example; substitute your model.

Read `architecture.md` sections 4–6 first. The order below keeps the app
green after every step.

## What you write per kind

| Piece | Where | Size |
| --- | --- | --- |
| Owner column, `shared_with_all`, two share tables | `models/<thing>.py` | ~25 lines |
| One `Shareable(...)` in `KINDS` | `service/sharing.py` | 10 lines |
| Read model | `service/wire.py` | a dataclass |
| Use cases taking the actor | `service/<things>.py` | list, page, create, update, delete |
| Handlers call the use cases | `states/…` | replaces the queries |
| `load_<thing>` | `states/share_state.py` | 4 lines |
| Share card on the detail page | `pages/…` | 2 lines |
| Migration | `alembic/versions/` | generated, one fix |

Sharing itself (the seven functions, the state, the card, merge and delete
of accounts) already exists and is not copied.

## 1. Model

```python
@ModelRegistry.register
class Item(SQLModel, table=True):
    ...
    # One owner, an ``authuser.id``. Who else may read it: service/sharing.py.
    owner_id: int = Field(foreign_key="authuser.id", index=True)
    shared_with_all: bool = False


@ModelRegistry.register
class ItemShare(SQLModel, table=True):
    """Read access to an item for one person."""

    __table_args__ = (UniqueConstraint("item_id", "user_id"),)

    id: int | None = Field(default=None, primary_key=True)
    item_id: int = Field(foreign_key="item.id", index=True)
    user_id: int = Field(foreign_key="authuser.id", index=True)


@ModelRegistry.register
class ItemGroupShare(SQLModel, table=True):
    """Read access to an item for every member of a group."""

    __table_args__ = (UniqueConstraint("item_id", "group_id"),)

    id: int | None = Field(default=None, primary_key=True)
    item_id: int = Field(foreign_key="item.id", index=True)
    group_id: int = Field(foreign_key="usergroup.id", index=True)
```

The column names `user_id`, `group_id` and `shared_with_all` are fixed; the
owner column and the target column are yours and named in the `Shareable`.
Every person column is a foreign key to `authuser.id` — that is how
`tests/test_people.py` finds one that merge and delete would miss. Export the
new classes from `models/__init__.py`.

A table that is owned but **not shareable** needs only the owner column and
an entry in `OWNER_COLUMNS` (`service/models.py`); its use cases compare
`row.owner_id` with the actor and raise `PermissionDeniedError`.

## 2. Declare the kind

`service/sharing.py`, at the marked place:

```python
from ..models import Item, ItemGroupShare, ItemShare

ITEMS = Shareable(
    kind="item",          # in messages and log events
    owner_word="owner",   # "Only the owner may change this item."
    model=Item,
    owner_column="owner_id",
    user_share=ItemShare,
    group_share=ItemGroupShare,
    target_column="item_id",
)

KINDS: tuple[Shareable[Any], ...] = (ITEMS,)
```

From here on merging and deleting accounts, and deleting a group, handle
items without further code.

## 3. Read model and use cases

`service/wire.py` — the fields the screens need, plus what the viewer may do:

```python
@dataclass(frozen=True)
class ItemInfo:
    id: int
    name: str
    ...
    mine: bool  # the viewer owns it; only then may they change it


def item_info(item: Item, viewer: int) -> ItemInfo: ...
```

`service/items.py`:

```python
def item_list(db: Session, me: int) -> list[ItemInfo]:
    """Everything ``me`` may read: own items and those shared."""
    query = select(Item).where(sharing.readable(sharing.ITEMS, me)).order_by(col(Item.id))
    return [item_info(item, me) for item in db.exec(query).all()]


def item_page(db: Session, me: int, item_id: int) -> ItemInfo:
    return item_info(sharing.get_viewable(db, sharing.ITEMS, me, item_id), me)


def create_item(db: Session, actor: int, form: ItemForm) -> ItemInfo:
    item = Item(**form.model_dump(), owner_id=actor)
    ...


def update_item(db: Session, actor: int, item_id: int, form: ItemForm) -> ItemInfo:
    item = sharing.owned(db, sharing.ITEMS, actor, item_id)
    ...


def delete_item(db: Session, actor: int, item_id: int) -> str:
    item = sharing.owned(db, sharing.ITEMS, actor, item_id)
    name = item.name
    sharing.drop_shares_of(db, sharing.ITEMS, item_id)   # shares go first
    db.delete(item)
    db.commit()
    return name
```

Three functions carry the rules — use them, never a bare `db.get`:

| Function | Meaning |
| --- | --- |
| `sharing.readable(KIND, me)` | SQL predicate for every list |
| `sharing.get_viewable(db, KIND, me, id)` | one row the viewer may read, or the refusal that does not say which |
| `sharing.owned(db, KIND, actor, id)` | one row the actor owns, or a refusal — first line of every write |

Re-export the public names from `service/__init__.py` and add the module to
`MAY_IMPORT` in `tests/test_service_layout.py`
(`"items": {"errors", "models", "wire", "sharing"}`).

## 4. Handlers

A handler gets the actor from the gate, hands a use case to `call`, and lets
refusals rise to `toast_errors`:

```python
from .. import service
from .handlers import call, toast_errors
from .people import actor_id


class ItemsState(rx.State):
    items: list[service.ItemInfo] = []

    @rx.event
    @toast_errors
    async def load(self):
        self.items = await call(service.item_list, await actor_id(self))

    @rx.event
    @toast_errors
    async def confirm_delete(self):
        ...
        name = await call(service.delete_item, await actor_id(self), item_id)
```

- No `rx.session`, `select`, `db.get` or model import in a state. Remove the
  module from `LEGACY` in `tests/test_architecture.py` once it is clean —
  the test then keeps it clean.
- `@toast_errors` sits directly under the event decorator on every handler
  that names the service or `as_id`; `tests/test_handlers.py` fails
  otherwise.
- Ids from route arguments and event payloads go through
  `utils/casting.as_id`.
- A detail page that should say "not found" instead of showing a toast
  catches the refusal itself, and says why on the first line:

  ```python
  try:
      self.item = await call(service.item_page, await actor_id(self), as_id(raw_id))
  except (service.PermissionDeniedError, InvalidInput):
      # Missing, not shared with this user, or not an id: the page says
      # "not found" for all three instead of a toast.
      self.not_found = True
  ```

- Hide what the viewer may not do — `rx.cond(item.mine, <edit and delete>)`
  — knowing that this is presentation; `sharing.owned` is the enforcement.

### A state that edits one open thing

When a whole state acts on the thing that is open (an editor), gate its
handlers once instead of relying on the service alone:

1. the page's `on_load` handler asks the service for the thing and keeps its
   owner in a private var: `_owner_id: int | None = None`;
2. `auth/authz.py` gets `owns_open_<thing>` (copy `owns_open_share_target`);
3. `auth/policy.py` gets `<thing>_owner_event = auth_event(auth=authz.owns_open_<thing>)`
   (and a `*_task` form with `background=True` if needed);
4. every changing handler uses that decorator instead of `@rx.event`;
5. `OWNER_GATED` in `tests/test_auth_policy.py` gets the state, its check
   and the handlers deliberately left to any signed-in user.

The check is a pre-filter that costs no query; the use case still calls
`sharing.owned`.

## 5. The share card

`states/share_state.py`:

```python
class ShareState(rx.State):
    if TYPE_CHECKING:
        item_id: str  # injected by the dynamic route — never assign it

    @rx.event
    @toast_errors
    async def load_item(self):
        await self._open(sharing.ITEMS, self.item_id)
```

The detail page (its route has the dynamic segment `[item_id]`):

```python
@rx.page(route=routes.ITEM_DETAIL_ROUTE, on_load=[ItemDetailState.load, ShareState.load_item])
def item_detail() -> rx.Component:
    ...
    rx.cond(ShareState.is_owner, share_card("People you share with can read this item.")),
```

Add `"load_item"` to `ShareState`'s open handlers in `OWNER_GATED`
(`tests/test_auth_policy.py`).

## 6. Migration

```bash
uv run reflex db makemigrations --message "items have owners and shares"
```

Open the generated revision before migrating:

- **Adding the owner column to an existing table fails on SQLite** with
  `ValueError: Constraint must have a name`. Name the foreign key in
  `upgrade()` and `downgrade()`:

  ```python
  batch_op.create_foreign_key("fk_item_owner_id_authuser", "authuser", ["owner_id"], ["id"])
  ...
  batch_op.drop_constraint("fk_item_owner_id_authuser", type_="foreignkey")
  ```

  A migration that fails halfway on SQLite leaves the tables it already
  created; drop those before running it again.
- **Existing rows have no owner.** `owner_id` is `NOT NULL` without a
  default, so the revision fails on a table with rows. Ask the user who gets
  them, then: add the column as nullable, `op.execute` an update that sets
  the chosen `authuser.id`, and alter it to `nullable=False` — all in that
  one revision.

Then `uv run reflex db migrate`, and fix tests that construct the model
without an owner.

## 7. Check

`scripts/check.sh --full`, then two browser sessions: the second user does
not see the first user's row in the list, gets "not found" on its URL, sees
it after it was shared, and has neither edit controls nor the share card.
