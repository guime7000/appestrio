import asyncio
import json

import pytest

from lora_daemon import backend_client, db
from lora_daemon.devices import LoraDeviceType, build_address
from lora_daemon.endpoint import EndpointResponder
from lora_daemon.messages import (
    PingType,
    decode_pong,
    encode_activate,
    encode_disable_agenda,
    encode_file_msg_chunk,
    encode_file_msg_start_versioned,
    encode_ping,
)
from lora_daemon.transport import LoopbackBus, LoopbackTransport

LUMESTRIO_3_ADDRESS = build_address(3, LoraDeviceType.LUMESTRIO)
OTHER_ADDRESS = build_address(9, LoraDeviceType.LUMESTRIO)


def _insert_device(conn, **overrides) -> None:
    row = {
        "uuid": "dev-uuid-1",
        "device_id": "lumestrio3",
        "device_name": "Lumestrio 3",
        "device_type": "lumestrio",
        "active": 0,
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
        "updated_at": "2026-09-26 00:00:00",
    }
    row.update(overrides)
    conn.execute(
        f"INSERT INTO devices ({', '.join(row)}) VALUES ({', '.join('?' for _ in row)})",
        list(row.values()),
    )
    conn.commit()


def _responder(conn, transport, **overrides) -> EndpointResponder:
    kwargs = {
        "conn": conn,
        "transport": transport,
        "own_address": LUMESTRIO_3_ADDRESS,
        "own_device_type": "lumestrio",
        "own_device_number": 3,
    }
    kwargs.update(overrides)
    return EndpointResponder(**kwargs)


def _read_active(conn) -> int:
    row = conn.execute("SELECT active FROM devices WHERE device_id = ?", ("lumestrio3",)).fetchone()
    return row["active"]


def _deliver(transport: LoopbackTransport, responder: EndpointResponder) -> None:
    """Mimics what PingScheduler's on_other_frame hook does in
    production: drain the transport once, hand each frame to the
    responder directly -- EndpointResponder has no polling loop of its
    own (see endpoint.py's module docstring for why).
    """
    for buf in transport.receive_all():
        responder.handle_frame(buf)


def test_ping_not_addressed_to_us_is_ignored(db_path: str) -> None:
    conn = db.connect(db_path)
    bus = LoopbackBus()
    transport = LoopbackTransport(bus)
    listener = LoopbackTransport(bus)
    responder = _responder(conn, transport)

    listener.send(
        encode_ping(
            agenda_disabled=False,
            ping_type=PingType.PLAIN,
            disable_wifi=False,
            slot_delay_centisec=50,
            addresses=[OTHER_ADDRESS],
        )
    )
    _deliver(transport, responder)

    assert listener.receive_all() == []


def test_ping_plain_replies_with_active_state(db_path: str) -> None:
    conn = db.connect(db_path)
    _insert_device(conn, active=1)
    bus = LoopbackBus()
    transport = LoopbackTransport(bus)
    listener = LoopbackTransport(bus)
    responder = _responder(conn, transport)

    listener.send(
        encode_ping(
            agenda_disabled=False,
            ping_type=PingType.PLAIN,
            disable_wifi=False,
            slot_delay_centisec=50,
            addresses=[LUMESTRIO_3_ADDRESS],
        )
    )
    _deliver(transport, responder)

    [frame] = listener.receive_all()
    pong = decode_pong(frame)
    assert pong.address == LUMESTRIO_3_ADDRESS
    assert pong.active is True


def test_ping_without_our_own_device_row_replies_inactive(db_path: str) -> None:
    conn = db.connect(db_path)  # no devices row at all yet -- fresh install
    bus = LoopbackBus()
    transport = LoopbackTransport(bus)
    listener = LoopbackTransport(bus)
    responder = _responder(conn, transport)

    listener.send(
        encode_ping(
            agenda_disabled=False,
            ping_type=PingType.PLAIN,
            disable_wifi=False,
            slot_delay_centisec=50,
            addresses=[LUMESTRIO_3_ADDRESS],
        )
    )
    _deliver(transport, responder)

    [frame] = listener.receive_all()
    pong = decode_pong(frame)
    assert pong.active is False


def test_ping_with_config_version_replies_with_applied_version(db_path: str) -> None:
    conn = db.connect(db_path)
    _insert_device(conn, config_version=42)
    bus = LoopbackBus()
    transport = LoopbackTransport(bus)
    listener = LoopbackTransport(bus)
    responder = _responder(conn, transport)

    listener.send(
        encode_ping(
            agenda_disabled=False,
            ping_type=PingType.WITH_CONFIG_VERSION,
            disable_wifi=False,
            slot_delay_centisec=50,
            addresses=[LUMESTRIO_3_ADDRESS],
        )
    )
    _deliver(transport, responder)

    [frame] = listener.receive_all()
    pong = decode_pong(frame, expect_config_version=True)
    assert pong.config_version == 42


def test_ping_with_missing_parts_reports_current_transfer_gaps(db_path: str) -> None:
    conn = db.connect(db_path)
    bus = LoopbackBus()
    transport = LoopbackTransport(bus)
    listener = LoopbackTransport(bus)
    responder = _responder(conn, transport)

    listener.send(encode_file_msg_start_versioned(3, [(LUMESTRIO_3_ADDRESS, 5)]))
    listener.send(encode_file_msg_chunk(1, b"middle"))
    _deliver(transport, responder)

    listener.send(
        encode_ping(
            agenda_disabled=False,
            ping_type=PingType.WITH_MISSING_PARTS,
            disable_wifi=False,
            slot_delay_centisec=50,
            addresses=[LUMESTRIO_3_ADDRESS],
        )
    )
    _deliver(transport, responder)

    frames = listener.receive_all()
    pong = decode_pong(frames[-1], expect_missing_parts=True)
    assert pong.missing_parts == (0, 2)


def test_activate_targeting_us_is_logged(
    db_path: str, caplog: pytest.LogCaptureFixture
) -> None:
    conn = db.connect(db_path)
    bus = LoopbackBus()
    transport = LoopbackTransport(bus)
    peer = LoopbackTransport(bus)
    responder = _responder(conn, transport)

    peer.send(encode_activate(True, [LUMESTRIO_3_ADDRESS]))
    with caplog.at_level("INFO"):
        _deliver(transport, responder)  # must not raise

    assert "ACTIVATE received for lumestrio3" in caplog.text


def test_activate_not_targeting_us_is_ignored(
    db_path: str, caplog: pytest.LogCaptureFixture
) -> None:
    conn = db.connect(db_path)
    bus = LoopbackBus()
    transport = LoopbackTransport(bus)
    peer = LoopbackTransport(bus)
    responder = _responder(conn, transport)

    peer.send(encode_activate(True, [OTHER_ADDRESS]))
    with caplog.at_level("INFO"):
        _deliver(transport, responder)

    assert "ACTIVATE received" not in caplog.text


def test_activate_targeting_us_writes_own_active_state(db_path: str) -> None:
    conn = db.connect(db_path)
    _insert_device(conn, active=0)
    bus = LoopbackBus()
    transport = LoopbackTransport(bus)
    peer = LoopbackTransport(bus)
    responder = _responder(conn, transport)
    assert _read_active(conn) == 0

    peer.send(encode_activate(True, [LUMESTRIO_3_ADDRESS]))
    _deliver(transport, responder)

    assert _read_active(conn) == 1


def test_activate_not_targeting_us_leaves_active_state_unchanged(db_path: str) -> None:
    conn = db.connect(db_path)
    _insert_device(conn, active=0)
    bus = LoopbackBus()
    transport = LoopbackTransport(bus)
    peer = LoopbackTransport(bus)
    responder = _responder(conn, transport)

    peer.send(encode_activate(True, [OTHER_ADDRESS]))
    _deliver(transport, responder)

    assert _read_active(conn) == 0


async def test_activate_targeting_us_notifies_backend(
    db_path: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = []

    async def fake_notify(device_id: str, active: bool, *, backend_url: str) -> None:
        calls.append((device_id, active, backend_url))

    monkeypatch.setattr(backend_client, "notify_activate", fake_notify)
    conn = db.connect(db_path)
    bus = LoopbackBus()
    transport = LoopbackTransport(bus)
    peer = LoopbackTransport(bus)
    responder = _responder(conn, transport, backend_url="http://example:1234")

    peer.send(encode_activate(True, [LUMESTRIO_3_ADDRESS]))
    _deliver(transport, responder)
    await asyncio.sleep(0)  # let the fire-and-forget task run

    assert calls == [("lumestrio3", True, "http://example:1234")]


def test_activate_without_running_event_loop_does_not_raise(db_path: str) -> None:
    # Sync unit tests (like every other test in this file) call
    # handle_frame with no event loop running -- must stay a no-op for
    # the backend notification, not raise RuntimeError.
    conn = db.connect(db_path)
    bus = LoopbackBus()
    transport = LoopbackTransport(bus)
    peer = LoopbackTransport(bus)
    responder = _responder(conn, transport)

    peer.send(encode_activate(True, [LUMESTRIO_3_ADDRESS]))
    _deliver(transport, responder)  # must not raise


def test_disable_agenda_sets_flag(db_path: str) -> None:
    conn = db.connect(db_path)
    bus = LoopbackBus()
    transport = LoopbackTransport(bus)
    peer = LoopbackTransport(bus)
    responder = _responder(conn, transport)
    assert responder.agenda_disabled is False

    peer.send(encode_disable_agenda(True))
    _deliver(transport, responder)

    assert responder.agenda_disabled is True


def test_file_msg_start_not_addressed_to_us_is_ignored(db_path: str) -> None:
    conn = db.connect(db_path)
    bus = LoopbackBus()
    transport = LoopbackTransport(bus)
    peer = LoopbackTransport(bus)
    responder = _responder(conn, transport)

    peer.send(encode_file_msg_start_versioned(2, [(OTHER_ADDRESS, 9)]))
    peer.send(encode_file_msg_chunk(0, b"a"))
    peer.send(encode_file_msg_chunk(1, b"b"))
    _deliver(transport, responder)

    assert conn.execute("SELECT COUNT(*) AS n FROM devices").fetchone()["n"] == 0


def test_file_msg_full_transfer_self_provisions_device(db_path: str) -> None:
    conn = db.connect(db_path)
    bus = LoopbackBus()
    transport = LoopbackTransport(bus)
    peer = LoopbackTransport(bus)
    responder = _responder(conn, transport)

    payload = json.dumps(
        {
            "config_version": 7,
            "device_name": "Le 3e lumestrio",
            "handles_audio": True,
            "handles_dmx": False,
            "audiofile": None,
            "group": None,
            "calendar": None,
        }
    ).encode("utf-8")
    chunk_size = 40
    chunks = [payload[i : i + chunk_size] for i in range(0, len(payload), chunk_size)]

    peer.send(encode_file_msg_start_versioned(len(chunks), [(LUMESTRIO_3_ADDRESS, 7)]))
    for index, chunk in enumerate(chunks):
        peer.send(encode_file_msg_chunk(index, chunk))
    _deliver(transport, responder)

    device = conn.execute(
        "SELECT * FROM devices WHERE device_id = 'lumestrio3'"
    ).fetchone()
    assert device is not None
    assert device["device_name"] == "Le 3e lumestrio"
    assert device["config_version"] == 7
