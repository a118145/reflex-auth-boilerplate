import sqlalchemy
from datetime import datetime, timezone
from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship


# ── Many-to-Many link table: which users have shared access to which entities ──
class EntityUserShareLink(SQLModel, table=True):
    entity_id: Optional[int] = Field(
        default=None,
        foreign_key="shareableentitymodel.id",
        primary_key=True,
    )
    user_id: Optional[int] = Field(
        default=None,
        foreign_key="usermodel.id",
        primary_key=True,
    )


# ── User ───────────────────────────────────────────────────────────────────────
class UserModel(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(nullable=False)
    abbreviation: Optional[str] = Field(default=None, nullable=True)
    pw_hash: str = Field(nullable=False)
    api_token: Optional[str] = Field(default=None, nullable=True)
    access_lvl: int = Field(default=0, nullable=False)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=sqlalchemy.DateTime(timezone=True),
        sa_column_kwargs={"server_default": sqlalchemy.func.now()},
        nullable=False,
    )

    # Navigate from user → their entities (no back_populates on entity side)
    owned_entities: List["ShareableEntityModel"] = Relationship(
        sa_relationship_kwargs={
            "foreign_keys": "[ShareableEntityModel.owner_id]",
        },
    )
    shared_entities: List["ShareableEntityModel"] = Relationship(
        link_model=EntityUserShareLink,
    )


# ── Base shareable entity (joined-table inheritance root) ──────────────────────
# Relationships are intentionally omitted here: SQLModel's metaclass cannot
# handle instrumented Mapped[...] types on JTI parent classes with Pydantic v2.
# Navigate owner/sharing via UserModel.owned_entities / UserModel.shared_entities,
# or query UserModel directly using owner_id.
class ShareableEntityModel(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    entity_type: str = Field(nullable=False)
    owner_id: Optional[int] = Field(
        default=None,
        foreign_key="usermodel.id",
        nullable=True,
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=sqlalchemy.DateTime(timezone=True),
        sa_column_kwargs={"server_default": sqlalchemy.func.now()},
        nullable=False,
    )

    __mapper_args__ = {
        "polymorphic_on": "entity_type",
        "polymorphic_identity": "base",
    }


# ── Example subclass: Document ─────────────────────────────────────────────────
class DocumentModel(ShareableEntityModel, table=True):
    id: Optional[int] = Field(
        default=None,
        foreign_key="shareableentitymodel.id",
        primary_key=True,
    )
    name: str = Field(nullable=False)
    content: Optional[str] = Field(default=None, nullable=True)

    __mapper_args__ = {"polymorphic_identity": "document"}


# ── Example subclass: Task ─────────────────────────────────────────────────────
class TaskModel(ShareableEntityModel, table=True):
    id: Optional[int] = Field(
        default=None,
        foreign_key="shareableentitymodel.id",
        primary_key=True,
    )
    title: str = Field(nullable=False)
    due_date: Optional[datetime] = Field(
        default=None,
        sa_type=sqlalchemy.DateTime(timezone=True),
        nullable=True,
    )
    is_done: bool = Field(default=False, nullable=False)

    __mapper_args__ = {"polymorphic_identity": "task"}
