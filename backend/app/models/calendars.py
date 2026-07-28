from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlmodel import JSON, Field, Relationship, SQLModel

from app.models.common import utcnow

if TYPE_CHECKING:
    from app.models.groups import Group


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


class CalendarCreate(SQLModel):
    label: str = Field(min_length=1, max_length=255)
    presets: dict[str, Any] | None
    days: dict[str, Any] | None


class CalendarUpdate(SQLModel):
    label: str | None = Field(default=None, min_length=1, max_length=255)
    presets: dict[str, Any] | None = None
    days: dict[str, Any] | None = None


class CalendarPublic(CalendarBase):
    uuid: UUID
    updated_at: datetime


class CalendarSummaryPublic(SQLModel):
    uuid: UUID
    label: str
    updated_at: datetime


class CalendarsPublic(SQLModel):
    data: list[CalendarSummaryPublic]
    count: int
