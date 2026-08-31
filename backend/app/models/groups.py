from datetime import datetime
from uuid import UUID, uuid4

from sqlmodel import Field, Relationship, SQLModel

from app.models.calendars import Calendar
from app.models.common import utcnow
from app.models.devices import Device


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
    handles_audio: bool
    handles_dmx: bool


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
