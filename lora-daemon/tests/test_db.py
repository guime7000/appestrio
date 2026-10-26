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


def test_get_lora_settings_default_row(db_path: str) -> None:
    conn = db.connect(db_path)

    settings = db.get_lora_settings(conn)

    # channel=0/speed=2 match relaystrio's fixed-in-firmware E32 config,
    # not legacy's own software default -- see
    # app/models/lora_settings.py's comment (backend).
    assert settings == db.LoraSettingsRow(
        is_active=False,
        ping_interval_s=5,
        clock_interval_s=60,
        channel=0,
        speed=2,
        fec=True,
        relaystrio_recurring_threshold_days=2,
    )


def test_get_lora_settings_reflects_updates(db_path: str) -> None:
    conn = db.connect(db_path)
    conn.execute("UPDATE lora_settings SET is_active = 1, ping_interval_s = 10 WHERE id = 1")
    conn.commit()

    settings = db.get_lora_settings(conn)

    assert settings.is_active is True
    assert settings.ping_interval_s == 10


def test_list_device_identities(db_path: str) -> None:
    conn = db.connect(db_path)
    _insert_device(conn, device_id="a", device_type="lumestrio")
    _insert_device(conn, uuid="dev-uuid-2", device_id="b", device_type="relaystrio")

    identities = db.list_device_identities(conn)

    assert {i.device_id: i.device_type for i in identities} == {
        "a": "lumestrio",
        "b": "relaystrio",
    }


def _config_payload(**overrides) -> dict:
    base = {
        "config_version": 7,
        "device_name": "Le 3e lumestrio",
        "handles_audio": True,
        "handles_dmx": False,
        "audiofile": "song.mp3",
        "group": "Jardin",
        "calendar": {
            "label": "Été",
            "weekdays": [6, 7],
            "ignition_presets": [
                {
                    "name": "Soirée",
                    "description": None,
                    "start_date": "01/06/2026",
                    "stop_date": "31/08/2026",
                    "start_time": "20:00",
                    "stop_time": "23:30",
                }
            ],
        },
    }
    base.update(overrides)
    return base


def test_apply_pushed_config_first_time_self_provisions(db_path: str) -> None:
    conn = db.connect(db_path)

    device_id = db.apply_pushed_config(
        conn, device_type="lumestrio", device_number=3, payload=_config_payload()
    )

    assert device_id == "lumestrio3"
    device = conn.execute("SELECT * FROM devices WHERE device_id = ?", (device_id,)).fetchone()
    assert device is not None
    assert device["device_name"] == "Le 3e lumestrio"
    assert device["device_type"] == "lumestrio"
    assert bool(device["handles_audio"]) is True
    assert bool(device["handles_dmx"]) is False
    assert device["audiofile"] == "song.mp3"
    assert device["config_version"] == 7
    assert device["synced_version"] == 7
    assert bool(device["active"]) is False  # never set from payload -- state, not config
    assert bool(device["is_master"]) is False

    group = conn.execute(
        "SELECT * FROM groups WHERE uuid = ?", (device["group_id"],)
    ).fetchone()
    assert group["label"] == "Jardin"

    calendar = conn.execute(
        "SELECT * FROM calendars WHERE uuid = ?", (group["calendar_id"],)
    ).fetchone()
    assert calendar["label"] == "Été"
    assert json.loads(calendar["weekdays"]) == [6, 7]

    presets = conn.execute(
        "SELECT * FROM ignition_presets WHERE calendar_id = ?", (calendar["uuid"],)
    ).fetchall()
    assert len(presets) == 1
    assert presets[0]["name"] == "Soirée"


def test_apply_pushed_config_without_group_or_calendar(db_path: str) -> None:
    conn = db.connect(db_path)

    device_id = db.apply_pushed_config(
        conn,
        device_type="lumestrio",
        device_number=5,
        payload=_config_payload(group=None, calendar=None),
    )

    device = conn.execute("SELECT * FROM devices WHERE device_id = ?", (device_id,)).fetchone()
    assert device["group_id"] is None
    assert conn.execute("SELECT COUNT(*) AS n FROM groups").fetchone()["n"] == 0
    assert conn.execute("SELECT COUNT(*) AS n FROM calendars").fetchone()["n"] == 0


def test_apply_pushed_config_second_call_updates_existing_device_row(db_path: str) -> None:
    conn = db.connect(db_path)
    db.apply_pushed_config(
        conn, device_type="lumestrio", device_number=3, payload=_config_payload()
    )

    db.apply_pushed_config(
        conn,
        device_type="lumestrio",
        device_number=3,
        payload=_config_payload(config_version=8, device_name="Renamed"),
    )

    rows = conn.execute("SELECT * FROM devices WHERE device_id = 'lumestrio3'").fetchall()
    assert len(rows) == 1  # updated in place, not duplicated
    assert rows[0]["device_name"] == "Renamed"
    assert rows[0]["config_version"] == 8


def test_apply_pushed_config_wipes_and_replaces_old_calendar_data(db_path: str) -> None:
    conn = db.connect(db_path)
    db.apply_pushed_config(
        conn, device_type="lumestrio", device_number=3, payload=_config_payload()
    )

    db.apply_pushed_config(
        conn,
        device_type="lumestrio",
        device_number=3,
        payload=_config_payload(
            config_version=8,
            group="Autre groupe",
            calendar={
                "label": "Hiver",
                "weekdays": [1],
                "ignition_presets": [],
            },
        ),
    )

    assert conn.execute("SELECT COUNT(*) AS n FROM groups").fetchone()["n"] == 1
    assert conn.execute("SELECT COUNT(*) AS n FROM calendars").fetchone()["n"] == 1
    assert conn.execute("SELECT COUNT(*) AS n FROM ignition_presets").fetchone()["n"] == 0
    group = conn.execute("SELECT * FROM groups").fetchone()
    assert group["label"] == "Autre groupe"
    calendar = conn.execute("SELECT * FROM calendars").fetchone()
    assert calendar["label"] == "Hiver"


def test_apply_pushed_config_preserves_active_state_on_update(db_path: str) -> None:
    conn = db.connect(db_path)
    db.apply_pushed_config(
        conn, device_type="lumestrio", device_number=3, payload=_config_payload()
    )
    conn.execute("UPDATE devices SET active = 1 WHERE device_id = 'lumestrio3'")
    conn.commit()

    db.apply_pushed_config(
        conn,
        device_type="lumestrio",
        device_number=3,
        payload=_config_payload(config_version=9),
    )

    row = conn.execute("SELECT active FROM devices WHERE device_id = 'lumestrio3'").fetchone()
    assert bool(row["active"]) is True  # untouched by the config push
