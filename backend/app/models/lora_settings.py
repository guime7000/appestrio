from datetime import datetime

from sqlmodel import Field, SQLModel

from app.models.common import utcnow

# Valid ranges mirror legacy's LoraState.ts validator (validateLoraState).
MAX_LORA_CHANNEL = 54
# Index into legacy's airDataRates == [0.3, 1.2, 2.4, 4.8, 9.6, 19.2] kbps.
NUM_AIR_DATA_RATES = 6
MIN_PING_INTERVAL_S = 1
MIN_CLOCK_INTERVAL_S = 1

# channel/speed match `relaystrio`'s E32 module, which is hardcoded in
# firmware to channel=0, air rate AIR_DATA_RATE_010_24 (speed index 2,
# 2.4kbps) and can never be reconfigured remotely (Legacy/Audits/
# relaystrio.md). Every device on one physical LoRa network must share
# the same channel/air-rate to hear each other at all -- it's the
# radio's own tuning, not a per-device setting -- so any site with a
# relaystrio unit present needs the whole network (master + every
# lumestrio) on these values; shipping them as the default means a
# freshly provisioned lumestrio needs no manual PATCH to join such a
# network. Not legacy's own software default (LoraState.ts's
# DefaultLoraState used channel=40/speed=3) -- see the migration that
# changed this (81b1c47cc2a5) and Lora_Rewrite_Plan.md for the history.
# ping/clock interval defaults are still legacy's own, unrelated to this.
DEFAULT_CHANNEL = 0
DEFAULT_SPEED = 2
DEFAULT_PING_INTERVAL_S = 5
DEFAULT_CLOCK_INTERVAL_S = 60


class LoraSettingsBase(SQLModel):
    is_active: bool = Field(default=False)
    channel: int = Field(default=DEFAULT_CHANNEL, ge=0, le=MAX_LORA_CHANNEL)
    speed: int = Field(default=DEFAULT_SPEED, ge=0, lt=NUM_AIR_DATA_RATES)
    fec: bool = Field(default=True)
    ping_interval_s: int = Field(default=DEFAULT_PING_INTERVAL_S, ge=MIN_PING_INTERVAL_S)
    clock_interval_s: int = Field(default=DEFAULT_CLOCK_INTERVAL_S, ge=MIN_CLOCK_INTERVAL_S)


class LoraSettings(LoraSettingsBase, table=True):
    __tablename__ = "lora_settings"

    # Deliberately not a UUID PK: this is a global singleton row (the
    # daemon's own radio configuration), not one of many, so the table
    # always has exactly one row addressed by this fixed id -- no "which
    # one", no list/create/delete routes, just GET/PATCH on id=1.
    id: int = Field(default=1, primary_key=True)
    updated_at: datetime = Field(default_factory=utcnow)


class LoraSettingsUpdate(SQLModel):
    is_active: bool | None = None
    channel: int | None = Field(default=None, ge=0, le=MAX_LORA_CHANNEL)
    speed: int | None = Field(default=None, ge=0, lt=NUM_AIR_DATA_RATES)
    fec: bool | None = None
    ping_interval_s: int | None = Field(default=None, ge=MIN_PING_INTERVAL_S)
    clock_interval_s: int | None = Field(default=None, ge=MIN_CLOCK_INTERVAL_S)


class LoraSettingsPublic(LoraSettingsBase):
    updated_at: datetime
