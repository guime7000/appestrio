import re
from datetime import datetime
from typing import TYPE_CHECKING, Optional
from uuid import UUID, uuid4

from pydantic import field_validator, model_validator
from sqlmodel import Field, Relationship, SQLModel

from app.models.common import utcnow

if TYPE_CHECKING:
    from app.models.calendars import Calendar

DATE_FORMAT = "%d/%m/%Y"
TIME_FORMAT = "%H:%M"

# strptime alone is lenient about leading zeros (e.g. accepts "1/1/2026" or
# "9:15"), so the exact-width shape is enforced with a regex first.
_DATE_RE = re.compile(r"^\d{2}/\d{2}/\d{4}$")
_TIME_RE = re.compile(r"^\d{2}:\d{2}$")


def parse_date(value: str) -> datetime:
    if not _DATE_RE.match(value):
        raise ValueError("must be a valid date in DD/MM/YYYY format")
    try:
        return datetime.strptime(value, DATE_FORMAT)
    except ValueError as exc:
        raise ValueError("must be a valid date in DD/MM/YYYY format") from exc


def parse_time(value: str) -> datetime:
    if not _TIME_RE.match(value):
        raise ValueError("must be a valid time in HH:MM format")
    try:
        return datetime.strptime(value, TIME_FORMAT)
    except ValueError as exc:
        raise ValueError("must be a valid time in HH:MM format") from exc


class IgnitionPresetBase(SQLModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    start_date: str = Field(max_length=10)
    stop_date: str = Field(max_length=10)
    start_time: str = Field(max_length=5)
    stop_time: str = Field(max_length=5)

    @field_validator("start_date", "stop_date")
    @classmethod
    def _validate_date_format(cls, value: str) -> str:
        parse_date(value)
        return value

    @field_validator("start_time", "stop_time")
    @classmethod
    def _validate_time_format(cls, value: str) -> str:
        parse_time(value)
        return value

    @model_validator(mode="after")
    def _validate_date_range(self) -> IgnitionPresetBase:
        if parse_date(self.start_date) > parse_date(self.stop_date):
            raise ValueError("start_date must not be after stop_date")
        return self


class IgnitionPreset(IgnitionPresetBase, table=True):
    __tablename__ = "ignition_presets"

    uuid: UUID = Field(default_factory=uuid4, primary_key=True)
    calendar_id: UUID = Field(foreign_key="calendars.uuid")
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    # See app/models/devices.py's Device.group comment for why this needs the
    # bracketed Optional["Calendar"] form rather than `Calendar | None`.
    calendar: Optional["Calendar"] = Relationship(back_populates="ignition_presets")  # noqa: UP037, UP045


class IgnitionPresetCreate(IgnitionPresetBase):
    calendar_id: UUID


class IgnitionPresetUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    start_date: str | None = None
    stop_date: str | None = None
    start_time: str | None = None
    stop_time: str | None = None
    calendar_id: UUID | None = None

    # Date ordering (start <= stop) can't be validated here in isolation since
    # this is a partial update -- see crud.update_ignition_preset, which
    # re-checks the merged start/stop pair against the stored record.
    @field_validator("start_date", "stop_date")
    @classmethod
    def _validate_date_format(cls, value: str | None) -> str | None:
        if value is not None:
            parse_date(value)
        return value

    @field_validator("start_time", "stop_time")
    @classmethod
    def _validate_time_format(cls, value: str | None) -> str | None:
        if value is not None:
            parse_time(value)
        return value


class IgnitionPresetPublic(IgnitionPresetBase):
    uuid: UUID
    calendar_id: UUID
    created_at: datetime
    updated_at: datetime


class IgnitionPresetsPublic(SQLModel):
    data: list[IgnitionPresetPublic]
    count: int
