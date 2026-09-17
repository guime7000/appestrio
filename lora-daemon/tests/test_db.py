import json
import sqlite3

import pytest

from lora_daemon import db


def _insert_device(conn: sqlite3.Connection, **overrides) -> None:
    row = {
        "uuid": "dev-uuid-1",
        "device_id": "lumestrio3",
        "device_name": "Lumestrio 3",
        "device_type": "lumestrio",
        "active": 1,
        "is_master": 0,
        "handles_audio": 0,
        "handles_dmx": 0,
        "audiofile": None,
        "ip": None,
        "master_ip": None,
        "group_id": None,
        "config_version": 1,
        "synced_version": 0,
        "last_seen": None,
        "last_roundtrip_ms": None,
        "updated_at": "2026-09-18 00:00:00",
    }
    row.update(overrides)
    conn.execute(
        f"INSERT INTO devices ({', '.join(row)}) VALUES ({', '.join('?' for _ in row)})",
        list(row.values()),
    )
    conn.commit()


def _insert_group(conn: sqlite3.Connection, **overrides) -> None:
    row = {"uuid": "group-uuid-1", "label": "Jardin", "calendar_id": None}
    row.update(overrides)
    conn.execute(
        f"INSERT INTO groups ({', '.join(row)}) VALUES ({', '.join('?' for _ in row)})",
        list(row.values()),
    )
    conn.commit()


def _insert_calendar(conn: sqlite3.Connection, **overrides) -> None:
    row = {"uuid": "cal-uuid-1", "label": "Été", "weekdays": json.dumps([6, 7])}
    row.update(overrides)
    conn.execute(
        f"INSERT INTO calendars ({', '.join(row)}) VALUES ({', '.join('?' for _ in row)})",
        list(row.values()),
    )
    conn.commit()


def _insert_preset(conn: sqlite3.Connection, **overrides) -> None:
    row = {
        "uuid": "preset-uuid-1",
        "calendar_id": "cal-uuid-1",
        "name": "Soirée",
        "description": None,
        "start_date": "01/06/2026",
        "stop_date": "31/08/2026",
        "start_time": "20:00",
        "stop_time": "23:30",
    }
    row.update(overrides)
    conn.execute(
        f"INSERT INTO ignition_presets ({', '.join(row)}) VALUES ({', '.join('?' for _ in row)})",
        list(row.values()),
    )
    conn.commit()


def test_connect_sets_pragmas(db_path: str) -> None:
    conn = db.connect(db_path)
    assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 5000


def test_connect_rejects_missing_columns(tmp_path) -> None:
    path = str(tmp_path / "broken.db")
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE devices (device_id TEXT)")
    conn.commit()
    conn.close()

    with pytest.raises(db.SchemaMismatchError, match="config_version"):
        db.connect(path)


def test_get_pending_sync_devices(db_path: str) -> None:
    conn = db.connect(db_path)
    _insert_device(conn, device_id="a", config_version=1, synced_version=0)
    _insert_device(conn, uuid="dev-uuid-2", device_id="b", config_version=3, synced_version=3)

    pending = db.get_pending_sync_devices(conn)

    assert [p.device_id for p in pending] == ["a"]
    assert pending[0].config_version == 1


def test_resolve_device_config_without_group(db_path: str) -> None:
    conn = db.connect(db_path)
    _insert_device(conn)

    config = db.resolve_device_config(conn, "lumestrio3")

    assert config is not None
    assert config.device_name == "Lumestrio 3"
    assert config.group_label is None
    assert config.calendar is None


def test_resolve_device_config_not_found(db_path: str) -> None:
    conn = db.connect(db_path)
    assert db.resolve_device_config(conn, "nosuchdevice") is None


def test_resolve_device_config_with_group_and_calendar(db_path: str) -> None:
    conn = db.connect(db_path)
    _insert_calendar(conn)
    _insert_preset(conn)
    _insert_group(conn, calendar_id="cal-uuid-1")
    _insert_device(conn, group_id="group-uuid-1")

    config = db.resolve_device_config(conn, "lumestrio3")

    assert config.group_label == "Jardin"
    assert config.calendar is not None
    assert config.calendar.label == "Été"
    assert config.calendar.weekdays == [6, 7]
    assert len(config.calendar.presets) == 1
    assert config.calendar.presets[0].name == "Soirée"


def test_resolve_device_config_group_without_calendar(db_path: str) -> None:
    conn = db.connect(db_path)
    _insert_group(conn)  # no calendar_id
    _insert_device(conn, group_id="group-uuid-1")

    config = db.resolve_device_config(conn, "lumestrio3")

    assert config.group_label == "Jardin"
    assert config.calendar is None


def test_mark_device_synced(db_path: str) -> None:
    conn = db.connect(db_path)
    _insert_device(conn)

    db.mark_device_synced(conn, "lumestrio3", 5)

    assert conn.execute(
        "SELECT synced_version FROM devices WHERE device_id = ?", ("lumestrio3",)
    ).fetchone()[0] == 5


def test_record_device_seen(db_path: str) -> None:
    conn = db.connect(db_path)
    _insert_device(conn)

    db.record_device_seen(conn, "lumestrio3", seen_at_iso="2026-09-18 12:00:00.000000", roundtrip_ms=42)

    row = conn.execute(
        "SELECT last_seen, last_roundtrip_ms FROM devices WHERE device_id = ?", ("lumestrio3",)
    ).fetchone()
    assert row[0] == "2026-09-18 12:00:00.000000"
    assert row[1] == 42


def test_reconcile_device_active(db_path: str) -> None:
    conn = db.connect(db_path)
    _insert_device(conn, active=1)

    db.reconcile_device_active(conn, "lumestrio3", False)

    assert conn.execute(
        "SELECT active FROM devices WHERE device_id = ?", ("lumestrio3",)
    ).fetchone()[0] == 0
