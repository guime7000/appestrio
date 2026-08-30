from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from pydantic import field_validator
from sqlmodel import JSON, Field, Relationship, SQLModel

from app.models.common import utcnow
from app.models.ignition_presets import IgnitionPreset, IgnitionPresetPublic

if TYPE_CHECKING:
    from app.models.groups import Group


def _validate_weekdays(value: list[int]) -> list[int]:
    if any(day < 1 or day > 7 for day in value):
        raise ValueError("weekdays must be integers between 1 (Monday) and 7 (Sunday)")
    return sorted(set(value))


class CalendarBase(SQLModel):
    label: str = Field(min_length=1, max_length=255)
    # ISO weekday numbers (1=Monday .. 7=Sunday) this calendar is active on.
    weekdays: list[int] = Field(default_factory=list, sa_type=JSON)

    @field_validator("weekdays")
    @classmethod
    def _check_weekdays(cls, value: list[int]) -> list[int]:
        return _validate_weekdays(value)


class Calendar(CalendarBase, table=True):
    __tablename__ = "calendars"

    uuid: UUID = Field(default_factory=uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    groups: list[Group] = Relationship(back_populates="calendar")
    # Presets can't exist without their calendar, so deleting a calendar
    # deletes its presets rather than leaving orphaned rows behind.
    ignition_presets: list[IgnitionPreset] = Relationship(
        back_populates="calendar",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class CalendarCreate(SQLModel):
    label: str = Field(min_length=1, max_length=255)
    weekdays: list[int] = Field(default_factory=list)

    @field_validator("weekdays")
    @classmethod
    def _check_weekdays(cls, value: list[int]) -> list[int]:
        return _validate_weekdays(value)


class CalendarUpdate(SQLModel):
    label: str | None = Field(default=None, min_length=1, max_length=255)
    weekdays: list[int] | None = None

    @field_validator("weekdays")
    @classmethod
    def _check_weekdays(cls, value: list[int] | None) -> list[int] | None:
        if value is None:
            return value
        return _validate_weekdays(value)


class CalendarPublic(CalendarBase):
    uuid: UUID
    updated_at: datetime
    ignition_presets: list[IgnitionPresetPublic] = []


class CalendarSummaryPublic(SQLModel):
    uuid: UUID
    label: str
    updated_at: datetime


class CalendarsPublic(SQLModel):
    data: list[CalendarSummaryPublic]
    count: int
