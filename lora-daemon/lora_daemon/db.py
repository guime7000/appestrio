"""Lightweight SQLite access to the shared appestrio backend database.

Deliberately raw stdlib `sqlite3`, not the backend's SQLModel classes --
`lora-daemon` and `backend` are separately deployed processes sharing one
SQLite file over a Docker volume; importing the backend's ORM classes
would couple two independently-versioned packages at the Python-class
level for the sake of a handful of fixed queries. This module owns every
SQL string the daemon uses, so it stays a single, small surface to diff
against backend migrations -- nothing here is generated or dynamic.

The daemon never runs migrations and never writes to any column it
doesn't own outright: `synced_version`, `last_seen`, `last_roundtrip_ms`,
and (once that design lands) `active`. Every other column is
backend-owned; this module only ever reads them.
"""

import json
import sqlite3
from dataclasses import dataclass

REQUIRED_DEVICE_COLUMNS = {
    "device_id",
    "device_name",
    "device_type",
    "active",
    "is_master",
    "handles_audio",
    "handles_dmx",
    "audiofile",
    "ip",
    "master_ip",
    "group_id",
    "config_version",
    "synced_version",
    "last_seen",
    "last_roundtrip_ms",
}


class SchemaMismatchError(RuntimeError):
    pass


def connect(db_path: str, *, busy_timeout_ms: int = 5000) -> sqlite3.Connection:
    """Open a connection with the pragmas a second writer on this shared
    file needs, and fail fast if the schema doesn't have what this
    daemon depends on (e.g. a backend migration ran but wasn't matched
    here, or vice versa).
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    # WAL is a database-file-level setting (likely already on from the
    # backend's side), but busy_timeout is per-connection -- this process
    # must set its own regardless of which side opened the file first.
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(f"PRAGMA busy_timeout={busy_timeout_ms}")
    _check_schema(conn)
    return conn


def _check_schema(conn: sqlite3.Connection) -> None:
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(devices)")}
    missing = REQUIRED_DEVICE_COLUMNS - columns
    if missing:
        raise SchemaMismatchError(
            f"devices table is missing expected column(s): {sorted(missing)} -- "
            "backend schema and lora-daemon's db.py have drifted apart"
        )


@dataclass(frozen=True)
class PendingDevice:
    device_id: str
    device_type: str
    config_version: int


def get_pending_sync_devices(conn: sqlite3.Connection) -> list[PendingDevice]:
    """The daemon's own version of crud.get_devices_pending_sync -- can't
    call backend Python across the process boundary, so this re-expresses
    the same `config_version != synced_version` comparison as SQL.
    """
    rows = conn.execute(
        """
        SELECT device_id, device_type, config_version
        FROM devices
        WHERE config_version != synced_version
        ORDER BY updated_at
        """
    ).fetchall()
    return [
        PendingDevice(
            device_id=row["device_id"],
            device_type=row["device_type"],
            config_version=row["config_version"],
        )
        for row in rows
    ]


@dataclass(frozen=True)
class IgnitionPresetRow:
    uuid: str
    name: str
    description: str | None
    start_date: str
    stop_date: str
    start_time: str
    stop_time: str


@dataclass(frozen=True)
class CalendarRow:
    uuid: str
    label: str
    weekdays: list[int]
    presets: list[IgnitionPresetRow]


@dataclass(frozen=True)
class DeviceConfigRow:
    device_id: str
    device_name: str
    device_type: str
    active: bool
    is_master: bool
    handles_audio: bool
    handles_dmx: bool
    audiofile: str | None
    ip: str | None
    master_ip: str | None
    config_version: int
    group_label: str | None
    calendar: CalendarRow | None


def resolve_device_config(conn: sqlite3.Connection, device_id: str) -> DeviceConfigRow | None:
    """Follows Device -> Group -> Calendar -> IgnitionPreset, the same
    relationship chain backend's `device_to_public`/`Device.group.calendar`
    walk via ORM relationships -- done here as explicit joins/queries
    since this connection has no ORM layer.
    """
    row = conn.execute(
        """
        SELECT d.device_id, d.device_name, d.device_type, d.active, d.is_master,
               d.handles_audio, d.handles_dmx, d.audiofile, d.ip, d.master_ip,
               d.config_version, g.label AS group_label, g.calendar_id AS calendar_id
        FROM devices d
        LEFT JOIN groups g ON g.uuid = d.group_id
        WHERE d.device_id = ?
        """,
        (device_id,),
    ).fetchone()
    if row is None:
        return None

    calendar = _resolve_calendar(conn, row["calendar_id"]) if row["calendar_id"] else None

    return DeviceConfigRow(
        device_id=row["device_id"],
        device_name=row["device_name"],
        device_type=row["device_type"],
        active=bool(row["active"]),
        is_master=bool(row["is_master"]),
        handles_audio=bool(row["handles_audio"]),
        handles_dmx=bool(row["handles_dmx"]),
        audiofile=row["audiofile"],
        ip=row["ip"],
        master_ip=row["master_ip"],
        config_version=row["config_version"],
        group_label=row["group_label"],
        calendar=calendar,
    )


def _resolve_calendar(conn: sqlite3.Connection, calendar_id: str) -> CalendarRow:
    row = conn.execute(
        "SELECT uuid, label, weekdays FROM calendars WHERE uuid = ?", (calendar_id,)
    ).fetchone()
    preset_rows = conn.execute(
        """
        SELECT uuid, name, description, start_date, stop_date, start_time, stop_time
        FROM ignition_presets
        WHERE calendar_id = ?
        ORDER BY start_date
        """,
        (calendar_id,),
    ).fetchall()
    presets = [
        IgnitionPresetRow(
            uuid=p["uuid"],
            name=p["name"],
            description=p["description"],
            start_date=p["start_date"],
            stop_date=p["stop_date"],
            start_time=p["start_time"],
            stop_time=p["stop_time"],
        )
        for p in preset_rows
    ]
    return CalendarRow(
        uuid=row["uuid"], label=row["label"], weekdays=json.loads(row["weekdays"]), presets=presets
    )


def mark_device_synced(conn: sqlite3.Connection, device_id: str, version: int) -> None:
    """Contract: `version` must come from the device's own self-reported
    version in a PONG, called on every PONG -- see crud.mark_device_synced's
    docstring backend-side; this is just the write, the caller (the not
    yet built scheduler) owns honoring that contract.
    """
    with conn:
        conn.execute(
            "UPDATE devices SET synced_version = ? WHERE device_id = ?", (version, device_id)
        )


def record_device_seen(
    conn: sqlite3.Connection, device_id: str, *, seen_at_iso: str, roundtrip_ms: int | None = None
) -> None:
    with conn:
        conn.execute(
            "UPDATE devices SET last_seen = ?, last_roundtrip_ms = ? WHERE device_id = ?",
            (seen_at_iso, roundtrip_ms, device_id),
        )


def reconcile_device_active(conn: sqlite3.Connection, device_id: str, active: bool) -> None:
    """Write side for the PONG -> Device.active reconciliation design note
    (item 9 of the backend-modifications plan) -- no caller yet, same
    status as mark_device_synced/record_device_seen until the scheduler
    exists to call it on every PONG.
    """
    with conn:
        conn.execute("UPDATE devices SET active = ? WHERE device_id = ?", (int(active), device_id))
