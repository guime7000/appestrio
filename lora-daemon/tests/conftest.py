import sqlite3

import pytest

# Mirrors the real appestrio backend schema (columns lora_daemon.db
# depends on) -- built with raw DDL rather than via Alembic/SQLModel, per
# the decision to keep lora-daemon independent of the backend package.
_SCHEMA = """
CREATE TABLE devices (
    uuid TEXT PRIMARY KEY,
    device_id TEXT UNIQUE NOT NULL,
    device_name TEXT NOT NULL,
    device_type TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    is_master INTEGER NOT NULL DEFAULT 0,
    handles_audio INTEGER NOT NULL DEFAULT 0,
    handles_dmx INTEGER NOT NULL DEFAULT 0,
    audiofile TEXT,
    ip TEXT,
    master_ip TEXT,
    group_id TEXT,
    config_version INTEGER NOT NULL DEFAULT 1,
    synced_version INTEGER NOT NULL DEFAULT 0,
    last_seen TEXT,
    last_roundtrip_ms INTEGER,
    updated_at TEXT NOT NULL
);

CREATE TABLE groups (
    uuid TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    calendar_id TEXT
);

CREATE TABLE calendars (
    uuid TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    weekdays TEXT NOT NULL
);

CREATE TABLE ignition_presets (
    uuid TEXT PRIMARY KEY,
    calendar_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    start_date TEXT NOT NULL,
    stop_date TEXT NOT NULL,
    start_time TEXT NOT NULL,
    stop_time TEXT NOT NULL
);
"""


@pytest.fixture
def db_path(tmp_path) -> str:
    path = str(tmp_path / "appestrio.db")
    conn = sqlite3.connect(path)
    conn.executescript(_SCHEMA)
    conn.commit()
    conn.close()
    return path
