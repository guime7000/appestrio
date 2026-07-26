from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlmodel import JSON, Field, Relationship, SQLModel


def utcnow() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# Calendar
# ---------------------------------------------------------------------------


class CalendarBase(SQLModel):
    label: str = Field(min_length=1, max_length=255)
    # e.g. {"setup1": {"start_time": "09:15", "end_time": "19:00"}, ...}
    presets: dict[str, Any] = Field(default_factory=dict, sa_type=JSON)
    # e.g. {"lundi": "setup1", "mardi": "setup1", ...}
    days: dict[str, Any] = Field(default_factory=dict, sa_type=JSON)


class Calendar(CalendarBase, table=True):
    __tablename__ = "calendars"

    uuid: UUID = Field(default_factory=uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    groups: list[Group] = Relationship(back_populates="calendar")


class CalendarCreate(CalendarBase):
    pass


class CalendarUpdate(SQLModel):
    label: str | None = Field(default=None, min_length=1, max_length=255)
    presets: dict[str, Any] | None = None
    days: dict[str, Any] | None = None


class CalendarPublic(CalendarBase):
    uuid: UUID
    updated_at: datetime


class CalendarsPublic(SQLModel):
    data: list[CalendarPublic]
    count: int


# ---------------------------------------------------------------------------
# Group
# ---------------------------------------------------------------------------


class GroupBase(SQLModel):
    label: str = Field(min_length=1, max_length=255)


class Group(GroupBase, table=True):
    __tablename__ = "groups"

    uuid: UUID = Field(default_factory=uuid4, primary_key=True)
    calendar_id: UUID | None = Field(default=None, foreign_key="calendars.uuid")
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    calendar: Calendar | None = Relationship(back_populates="groups")
    devices: list[Device] = Relationship(back_populates="group")


class GroupCreate(GroupBase):
    calendar_id: UUID | None = None


class GroupUpdate(SQLModel):
    label: str | None = Field(default=None, min_length=1, max_length=255)
    calendar_id: UUID | None = None


class GroupDevicePublic(SQLModel):
    uuid: UUID
    device_id: str
    device_name: str
    active: bool


class GroupPublic(GroupBase):
    uuid: UUID
    calendar_id: UUID | None = None
    updated_at: datetime
    devices: list[GroupDevicePublic] = []


class GroupsPublic(SQLModel):
    data: list[GroupPublic]
    count: int


class GroupDevicesUpdate(SQLModel):
    device_uuids: list[UUID]


# ---------------------------------------------------------------------------
# Device (Lumestrio)
# ---------------------------------------------------------------------------


class DeviceBase(SQLModel):
    device_id: str = Field(index=True, unique=True, min_length=1, max_length=255)
    device_name: str = Field(min_length=1, max_length=255)
    active: bool = Field(default=True)
    audiofile: str | None = Field(default=None, max_length=255)
    ip: str | None = Field(default=None, max_length=45)
    master_ip: str | None = Field(default=None, max_length=45)


class Device(DeviceBase, table=True):
    __tablename__ = "devices"

    uuid: UUID = Field(default_factory=uuid4, primary_key=True)
    group_id: UUID | None = Field(default=None, foreign_key="groups.uuid")
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    group: Group | None = Relationship(back_populates="devices")


class DeviceCreate(DeviceBase):
    group_id: UUID | None = None


class DeviceUpdate(SQLModel):
    device_id: str | None = Field(default=None, min_length=1, max_length=255)
    device_name: str | None = Field(default=None, min_length=1, max_length=255)
    active: bool | None = None
    audiofile: str | None = None
    ip: str | None = None
    master_ip: str | None = None
    group_id: UUID | None = None


class DevicePublic(SQLModel):
    uuid: UUID
    device_id: str
    device_name: str
    active: bool
    # Denormalized for the client: the group's label (not its uuid), and the
    # calendar reached through that group, per the Lumestrio spec payload.
    group: str | None = None
    calendar: CalendarPublic | None = None
    audiofile: str | None = None
    ip: str | None = None
    master_ip: str | None = None
    updated_at: datetime


class DevicesPublic(SQLModel):
    data: list[DevicePublic]
    count: int


class Message(SQLModel):
    message: str
