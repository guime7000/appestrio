"""The config payload pushed to `lumestrio` devices over FILE_MSG.

No legacy wire-compatibility constraint applies here (master<->lumestrio
is entirely new code on both ends -- see Lora_Rewrite_Plan.md's
lumestrio-clarification note), so this deliberately mirrors the shape of
`DevicePublic`/`CalendarPublic`/`IgnitionPresetPublic` from
`appestrio/backend` field-for-field, rather than inventing a third
format: a lumestrio endpoint applies a pushed config by calling its own
local `POST`/`PATCH /devices/`, so handing it JSON shaped like what that
endpoint already speaks means one format to maintain, not two.

This module only builds and serializes the payload from a
`db.DeviceConfigRow` -- it says nothing about how the receiving end
applies it (that's the lumestrio-side daemon's job, not yet built) and
nothing about `relaystrio` (a completely different, legacy-compatible
`Agenda` JSON shape, deliberately deferred -- see the plan doc).

`config_version` is **not** a field mirrored from `DevicePublic` (which
doesn't expose it -- see app/models/devices.py) but a top-level field of
this payload: it's what the receiving device stores locally and echoes
back in PONG per the config_version design (Lora_Rewrite_Plan.md §9.7).
"""

import json
from dataclasses import asdict, dataclass, field

from .db import DeviceConfigRow


@dataclass(frozen=True)
class IgnitionPresetPayload:
    name: str
    description: str | None
    start_date: str
    stop_date: str
    start_time: str
    stop_time: str


@dataclass(frozen=True)
class CalendarPayload:
    label: str
    weekdays: list[int]
    ignition_presets: list[IgnitionPresetPayload] = field(default_factory=list)


@dataclass(frozen=True)
class DeviceConfigPayload:
    config_version: int
    device_name: str
    device_type: str
    active: bool
    is_master: bool
    handles_audio: bool
    handles_dmx: bool
    audiofile: str | None
    ip: str | None
    master_ip: str | None
    group: str | None
    calendar: CalendarPayload | None

    def to_json_bytes(self) -> bytes:
        return json.dumps(asdict(self), separators=(",", ":")).encode("utf-8")


def build_device_config_payload(row: DeviceConfigRow) -> DeviceConfigPayload:
    calendar = None
    if row.calendar is not None:
        calendar = CalendarPayload(
            label=row.calendar.label,
            weekdays=row.calendar.weekdays,
            ignition_presets=[
                IgnitionPresetPayload(
                    name=p.name,
                    description=p.description,
                    start_date=p.start_date,
                    stop_date=p.stop_date,
                    start_time=p.start_time,
                    stop_time=p.stop_time,
                )
                for p in row.calendar.presets
            ],
        )

    return DeviceConfigPayload(
        config_version=row.config_version,
        device_name=row.device_name,
        device_type=row.device_type,
        active=row.active,
        is_master=row.is_master,
        handles_audio=row.handles_audio,
        handles_dmx=row.handles_dmx,
        audiofile=row.audiofile,
        ip=row.ip,
        master_ip=row.master_ip,
        group=row.group_label,
        calendar=calendar,
    )
