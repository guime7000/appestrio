from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional
from uuid import UUID, uuid4

from sqlalchemy import Enum as SAEnum
from sqlalchemy import Index, text
from sqlmodel import Field, Relationship, SQLModel

from app.models.calendars import CalendarPublic
from app.models.common import utcnow

if TYPE_CHECKING:
    from app.models.groups import Group


class DeviceType(str, Enum):
    LUMESTRIO = "lumestrio"
    RELAYSTRIO = "relaystrio"


# How many devices of each type can exist. Not a hardware limit (the LoRa
# address is one byte, with 255 reserved for broadcast) -- it's the
# legacy-chosen ceiling, kept here as the single place that defines it.
MAX_DEVICES_PER_TYPE = 32

# Explicit type -> LoRa address-index mapping. Deliberately not derived from
# DeviceType's enum declaration order (LUMESTRIO is declared first above,
# which would silently invert this if position were used instead). Matches
# legacy's LoraDeviceType.Relaystrio=0/Lumestrio=1, which the burger
# firmware also hardcodes.
LORA_TYPE_INDEX: dict[DeviceType, int] = {
    DeviceType.RELAYSTRIO: 0,
    DeviceType.LUMESTRIO: 1,
}


class DeviceBase(SQLModel):
    device_name: str = Field(min_length=1, max_length=255)
    # values_callable stores/reads the enum's *value* ("lumestrio") instead of
    # SQLAlchemy's default of the member *name* ("LUMESTRIO"), matching the
    # lowercase strings the API and the migration's backfill both use.
    device_type: DeviceType = Field(
        sa_type=SAEnum(
            DeviceType, values_callable=lambda enum: [e.value for e in enum], name="devicetype"
        )
    )
    active: bool = Field(default=True)
    is_master: bool = Field(default=False)
    handles_audio: bool = Field(default=False)
    handles_dmx: bool = Field(default=False)
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
    device_id: str = Field(index=True, unique=True, min_length=1, max_length=255)
    group_id: UUID | None = Field(default=None, foreign_key="groups.uuid")
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    # LoRa config-sync bookkeeping (see Lora_Rewrite_Plan.md's config_version
    # section). config_version is master's authoritative "current desired
    # config" counter for this device, bumped by crud.py whenever anything in
    # its resolved-config dependency chain changes (own row, group
    # membership, group's calendar, that calendar's weekdays/presets).
    # synced_version is the last value the LoRa daemon has confirmed the
    # device actually applied (via PONG) -- not written anywhere yet, since
    # the daemon doesn't exist. A device is "pending sync" whenever the two
    # differ; a freshly created device starts pending (1 vs 0) since nothing
    # has ever been pushed to it.
    config_version: int = Field(default=1)
    synced_version: int = Field(default=0)

    # SQLAlchemy's own annotation parser (used to infer the relationship
    # target here) only understands bracketed generics (Optional[X]/List[X]),
    # not PEP 604 `X | None` syntax, when X isn't otherwise importable at
    # module load time (Group lives in groups.py, which imports this module
    # first -- see app/models/__init__.py for the load order and rebuild).
    group: Optional["Group"] = Relationship(back_populates="devices")  # noqa: UP037, UP045


class DeviceCreate(DeviceBase):
    group_id: UUID | None = None
    # device_id is derived server-side from device_type + device_number
    # (e.g. "lumestrio3"), never supplied directly -- this is what keeps the
    # LoRa address derivation safe (parseable and unique by construction).
    device_number: int = Field(ge=0, lt=MAX_DEVICES_PER_TYPE)


class DeviceUpdate(SQLModel):
    # device_id is immutable after creation: it's about to become the thing
    # the LoRa address is derived from, so a live, radio-addressed device
    # must never be renamed out from under its assigned address.
    device_name: str | None = Field(default=None, min_length=1, max_length=255)
    device_type: DeviceType | None = None
    active: bool | None = None
    is_master: bool | None = None
    handles_audio: bool | None = None
    handles_dmx: bool | None = None
    audiofile: str | None = None
    ip: str | None = None
    master_ip: str | None = None
    group_id: UUID | None = None


class DevicePublic(SQLModel):
    # No `uuid`: the device's DB primary key is internal only. `device_id`
    # (unique, immutable, see DeviceUpdate above) is the identifier clients
    # use to address a device, both here and in the API's URL paths.
    device_id: str
    device_name: str
    device_type: DeviceType
    active: bool
    is_master: bool
    handles_audio: bool
    handles_dmx: bool
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


class FreeDeviceNumbers(SQLModel):
    relaystrio: list[int]
    lumestrio: list[int]


class DeviceBulkDeleteRequest(SQLModel):
    device_ids: list[str] = Field(min_length=1)
