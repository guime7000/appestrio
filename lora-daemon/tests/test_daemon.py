import asyncio

import pytest

from lora_daemon import backend_client, daemon, db
from lora_daemon.devices import LoraDeviceType, build_address
from lora_daemon.messages import PingType, decode_pong, encode_activate, encode_ping
from lora_daemon.transport import LoopbackBus, LoopbackTransport


def test_required_env_raises_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LORA_DB_PATH", raising=False)
    with pytest.raises(RuntimeError, match="LORA_DB_PATH"):
        daemon._required_env("LORA_DB_PATH")


def test_required_env_raises_when_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LORA_DB_PATH", "")
    with pytest.raises(RuntimeError, match="LORA_DB_PATH"):
        daemon._required_env("LORA_DB_PATH")


def test_required_env_returns_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LORA_DB_PATH", "/tmp/appestrio.db")
    assert daemon._required_env("LORA_DB_PATH") == "/tmp/appestrio.db"


def test_resolve_own_identity_recognizes_lumestrio_hostname(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("LORA_HOSTNAME", "lumestrio3")
    with caplog.at_level("INFO"):
        identity = daemon._resolve_own_identity()
    assert "device_id=lumestrio3" in caplog.text
    assert identity == (LoraDeviceType.LUMESTRIO, 3)


def test_resolve_own_identity_is_non_fatal_for_unrecognized_hostname(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("LORA_HOSTNAME", "raspberrypi")
    with caplog.at_level("INFO"):
        identity = daemon._resolve_own_identity()  # must not raise
    assert "not a lumestrio endpoint" in caplog.text
    assert identity is None


async def test_run_daemon_starts_scheduler_and_stops_cleanly(db_path: str) -> None:
    conn = db.connect(db_path)
    bus = LoopbackBus()
    transport = LoopbackTransport(bus)
    stop = asyncio.Event()

    task = asyncio.create_task(
        daemon.run_daemon(conn=conn, transport=transport, stop=stop, control_port=0)
    )
    await asyncio.sleep(0.05)
    assert not task.done()  # still running, blocked on stop.wait()

    stop.set()
    await asyncio.wait_for(task, timeout=1.0)
    assert task.done()
    assert task.exception() is None


async def test_run_daemon_cancels_scheduler_task_on_stop(db_path: str) -> None:
    conn = db.connect(db_path)
    bus = LoopbackBus()
    transport = LoopbackTransport(bus)
    conn.execute("UPDATE lora_settings SET is_active = 1 WHERE id = 1")
    conn.commit()
    stop = asyncio.Event()

    task = asyncio.create_task(
        daemon.run_daemon(conn=conn, transport=transport, stop=stop, control_port=0)
    )
    await asyncio.sleep(0.05)
    stop.set()

    # No CancelledError should escape run_daemon -- it's caught internally.
    await asyncio.wait_for(task, timeout=1.0)


async def test_run_daemon_starts_endpoint_responder_when_own_identity_given(
    db_path: str,
) -> None:
    conn = db.connect(db_path)
    bus = LoopbackBus()
    transport = LoopbackTransport(bus)
    listener = LoopbackTransport(bus)
    stop = asyncio.Event()

    task = asyncio.create_task(
        daemon.run_daemon(
            conn=conn,
            transport=transport,
            stop=stop,
            control_port=0,
            own_identity=(LoraDeviceType.LUMESTRIO, 3),
        )
    )
    try:
        own_address = build_address(3, LoraDeviceType.LUMESTRIO)
        listener.send(
            encode_ping(
                agenda_disabled=False,
                ping_type=PingType.PLAIN,
                disable_wifi=False,
                slot_delay_centisec=50,
                addresses=[own_address],
            )
        )
        await asyncio.sleep(0.2)
        [frame] = listener.receive_all()
        assert decode_pong(frame).address == own_address
    finally:
        stop.set()
        await asyncio.wait_for(task, timeout=1.0)


async def test_run_daemon_wires_backend_url_into_activate_notification(
    db_path: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = []

    async def fake_notify(device_id: str, active: bool, *, backend_url: str) -> None:
        calls.append((device_id, active, backend_url))

    monkeypatch.setattr(backend_client, "notify_activate", fake_notify)

    conn = db.connect(db_path)
    bus = LoopbackBus()
    transport = LoopbackTransport(bus)
    listener = LoopbackTransport(bus)
    stop = asyncio.Event()

    task = asyncio.create_task(
        daemon.run_daemon(
            conn=conn,
            transport=transport,
            stop=stop,
            control_port=0,
            own_identity=(LoraDeviceType.LUMESTRIO, 3),
            backend_url="http://example:1234",
        )
    )
    try:
        own_address = build_address(3, LoraDeviceType.LUMESTRIO)
        listener.send(encode_activate(True, [own_address]))
        await asyncio.sleep(0.2)
        assert calls == [("lumestrio3", True, "http://example:1234")]
    finally:
        stop.set()
        await asyncio.wait_for(task, timeout=1.0)
