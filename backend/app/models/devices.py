from datetime import datetime
from typing import TYPE_CHECKING, Optional
from uuid import UUID, uuid4

from sqlalchemy import Index, text
from sqlmodel import Field, Relationship, SQLModel

from app.models.calendars import CalendarPublic
from app.models.common import utcnow

if TYPE_CHECKING:
    from app.models.groups import Group


class DeviceBase(SQLModel):
    device_id: str = Field(index=True, unique=True, min_length=1, max_length=255)
    device_name: str = Field(min_length=1, max_length=255)
    active: bool = Field(default=True)
    is_master: bool = Field(default=False)
    audiofile: str | None = Field(default=None, max_length=255)
    ip: str | None = Field(default=None, max_length=45)
    master_ip: str | None = Field(default=None, max_length=45)


class Device(DeviceBase, table=True):
    __tablename__ = "devices"
    # Partial unique index: only rows where is_master is true are compared,
    # so any number of non-master devices coexist but at most one can be master.
    __table_args__ = (
        Index(
            "ix_devices_single_master",
            "is_master",
            unique=True,
            sqlite_where=text("is_master = 1"),
            postgresql_where=text("is_master = true"),
        ),
    )

    uuid: UUID = Field(default_factory=uuid4, primary_key=True)
    group_id: UUID | None = Field(default=None, foreign_key="groups.uuid")
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    # SQLAlchemy's own annotation parser (used to infer the relationship
    # target here) only understands bracketed generics (Optional[X]/List[X]),
    # not PEP 604 `X | None` syntax, when X isn't otherwise importable at
    # module load time (Group lives in groups.py, which imports this module
    # first -- see app/models/__init__.py for the load order and rebuild).
    group: Optional["Group"] = Relationship(back_populates="devices")  # noqa: UP037, UP045


class DeviceCreate(DeviceBase):
    group_id: UUID | None = None


class DeviceUpdate(SQLModel):
    device_id: str | None = Field(default=None, min_length=1, max_length=255)
    device_name: str | None = Field(default=None, min_length=1, max_length=255)
    active: bool | None = None
    is_master: bool | None = None
    audiofile: str | None = None
    ip: str | None = None
    master_ip: str | None = None
    group_id: UUID | None = None


class DevicePublic(SQLModel):
    uuid: UUID
    device_id: str
    device_name: str
    active: bool
    is_master: bool
    # Denormalized for the client: the group's label and uuid (so the client
    # can link to the group's detail), and the calendar reached through that
    # group, per the Lumestrio spec payload.
    group: str | None = None
    group_id: UUID | None = None
    calendar: CalendarPublic | None = None
    audiofile: str | None = None
    ip: str | None = None
    master_ip: str | None = None
    updated_at: datetime


class DevicesPublic(SQLModel):
    data: list[DevicePublic]
    count: int
