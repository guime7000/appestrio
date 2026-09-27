import asyncio
import contextlib

import pytest

from lora_daemon import db, hexconf, orchestration
from lora_daemon.devices import LoraDeviceType, build_address
from lora_daemon.messages import (
    FILE_MSG_START,
    MessageType,
    PingType,
    decode_activate,
    decode_file_msg,
    decode_file_msg_start_versioned,
    decode_ping,
    encode_pong,
)
from lora_daemon.scheduler import PingScheduler
from lora_daemon.transport import LoopbackBus, LoopbackTransport

LUMESTRIO_3_ADDRESS = build_address(3, LoraDeviceType.LUMESTRIO)


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


async def _cancel(task: asyncio.Task) -> None:
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task


# --- run_hex_conf_sync_forever --------------------------------------------


async def test_run_hex_conf_sync_forever_pushes_immediately_on_startup(db_path: str) -> None:
    # default row: channel=0/speed=2 (matches relaystrio's fixed radio --
    # see app/models/lora_settings.py's comment, backend), fec=1.
    conn = db.connect(db_path)
    bus = LoopbackBus()
    transport = LoopbackTransport(bus)
    expected = hexconf.build_hex_conf(channel=0, speed=2, fec=True)

    task = asyncio.create_task(
        orchestration.run_hex_conf_sync_forever(conn=conn, transport=transport, interval_s=10)
    )
    await asyncio.sleep(0.05)
    await _cancel(task)

    assert transport.last_hex_conf == expected


async def test_run_hex_conf_sync_forever_repushes_only_on_change(db_path: str) -> None:
    conn = db.connect(db_path)
    bus = LoopbackBus()
    transport = LoopbackTransport(bus)
    default_conf = hexconf.build_hex_conf(channel=0, speed=2, fec=True)

    task = asyncio.create_task(
        orchestration.run_hex_conf_sync_forever(conn=conn, transport=transport, interval_s=0.02)
    )
    await asyncio.sleep(0.05)
    assert transport.last_hex_conf == default_conf

    transport.last_hex_conf = None  # prove the next tick doesn't just re-push unconditionally
    await asyncio.sleep(0.05)
    await _cancel(task)

    assert transport.last_hex_conf is None  # unchanged settings -> no re-push

    conn.execute("UPDATE lora_settings SET channel = 12 WHERE id = 1")
    conn.commit()
    task = asyncio.create_task(
        orchestration.run_hex_conf_sync_forever(conn=conn, transport=transport, interval_s=10)
    )
    await asyncio.sleep(0.05)
    await _cancel(task)

    assert transport.last_hex_conf != default_conf  # changed channel -> pushed a new value


# --- send_activate ----------------------------------------------------------


def test_send_activate_broadcast_pauses_and_resumes(db_path: str) -> None:
    conn = db.connect(db_path)
    bus = LoopbackBus()
    transport = LoopbackTransport(bus)
    listener = LoopbackTransport(bus)
    scheduler = PingScheduler(conn=conn, transport=transport)

    orchestration.send_activate(transport=transport, scheduler=scheduler, active=True)

    assert scheduler._paused is False  # resumed after sending
    [frame] = listener.receive_all()
    activate = decode_activate(frame)
    assert activate.active is True


def test_send_activate_single_target_does_not_pause(db_path: str) -> None:
    conn = db.connect(db_path)
    bus = LoopbackBus()
    transport = LoopbackTransport(bus)
    scheduler = PingScheduler(conn=conn, transport=transport)
    scheduler.pause()  # pre-existing pause must survive an untouched single-target send

    orchestration.send_activate(
        transport=transport, scheduler=scheduler, active=False, addresses=[3]
    )

    assert scheduler._paused is True


# --- clock sync ---------------------------------------------------------


async def test_run_clock_sync_forever_sends_when_active(db_path: str) -> None:
    conn = db.connect(db_path)
    conn.execute("UPDATE lora_settings SET is_active = 1, clock_interval_s = 1 WHERE id = 1")
    conn.commit()
    bus = LoopbackBus()
    transport = LoopbackTransport(bus)
    listener = LoopbackTransport(bus)

    task = asyncio.create_task(orchestration.run_clock_sync_forever(conn=conn, transport=transport))
    await asyncio.sleep(0.1)
    await _cancel(task)

    frames = listener.receive_all()
    assert len(frames) == 1
    assert frames[0][0] == int(MessageType.SYNC)


async def test_run_clock_sync_forever_skips_when_inactive(db_path: str) -> None:
    conn = db.connect(db_path)  # lora_settings.is_active defaults to False
    bus = LoopbackBus()
    transport = LoopbackTransport(bus)
    listener = LoopbackTransport(bus)

    task = asyncio.create_task(orchestration.run_clock_sync_forever(conn=conn, transport=transport))
    await asyncio.sleep(0.05)
    await _cancel(task)

    assert listener.receive_all() == []


# --- sync_device_config ---------------------------------------------------


async def test_sync_device_config_unknown_device(db_path: str) -> None:
    conn = db.connect(db_path)
    bus = LoopbackBus()
    scheduler = PingScheduler(conn=conn, transport=LoopbackTransport(bus))

    result = await orchestration.sync_device_config(
        conn=conn,
        transport=LoopbackTransport(bus),
        scheduler=scheduler,
        device_id="nosuchdevice",
    )

    assert result is False


async def test_sync_device_config_rejects_relaystrio(db_path: str) -> None:
    conn = db.connect(db_path)
    _insert_device(conn, device_id="relaystrio1", device_type="relaystrio")
    bus = LoopbackBus()
    scheduler = PingScheduler(conn=conn, transport=LoopbackTransport(bus))

    result = await orchestration.sync_device_config(
        conn=conn,
        transport=LoopbackTransport(bus),
        scheduler=scheduler,
        device_id="relaystrio1",
    )

    assert result is False


async def test_sync_device_config_happy_path(db_path: str) -> None:
    conn = db.connect(db_path)
    _insert_device(conn, config_version=5, synced_version=0)
    conn.execute("UPDATE lora_settings SET is_active = 1 WHERE id = 1")
    conn.commit()

    bus = LoopbackBus()
    transport = LoopbackTransport(bus)
    listener = LoopbackTransport(bus)  # sniffs the transfer to verify its content
    device = LoopbackTransport(bus)  # simulates the real lumestrio device replying
    scheduler = PingScheduler(conn=conn, transport=transport)

    ping_task = asyncio.create_task(scheduler.run_forever())

    async def device_responder() -> None:
        while True:
            for frame in device.receive_all():
                if not frame or frame[0] != int(MessageType.PING):
                    continue
                ping = decode_ping(frame)
                if ping.ping_type == PingType.WITH_MISSING_PARTS:
                    device.send(
                        encode_pong(address=LUMESTRIO_3_ADDRESS, active=True, missing_parts=[])
                    )
            await asyncio.sleep(0.01)

    responder_task = asyncio.create_task(device_responder())

    try:
        result = await orchestration.sync_device_config(
            conn=conn,
            transport=transport,
            scheduler=scheduler,
            device_id="lumestrio3",
            chunk_delay_s=0.01,
            missing_check_interval_s=0.05,
            missing_reply_timeout_s=0.5,
            max_missing_checks=3,
        )
    finally:
        await _cancel(ping_task)
        await _cancel(responder_task)

    assert result is True
    row = conn.execute(
        "SELECT synced_version FROM devices WHERE device_id = ?", ("lumestrio3",)
    ).fetchone()
    assert row[0] == 5

    # Verify what was actually sent, not just the end result.
    num_parts = None
    chunks: dict[int, bytes] = {}
    for frame in listener.receive_all():
        if not frame or frame[0] != int(MessageType.FILE_MSG):
            continue
        if frame[1] == FILE_MSG_START:
            start = decode_file_msg_start_versioned(frame)
            assert start.targets == ((LUMESTRIO_3_ADDRESS, 5),)
            num_parts = start.num_parts
        else:
            chunk = decode_file_msg(frame)
            chunks[chunk.index] = chunk.data
    assert num_parts == len(chunks)
    body = b"".join(chunks[i] for i in range(num_parts))
    assert b'"config_version":5' in body
    assert b'"device_name":"Lumestrio 3"' in body


async def test_sync_device_config_gives_up_when_no_reply(db_path: str) -> None:
    conn = db.connect(db_path)
    _insert_device(conn, config_version=5, synced_version=0)
    conn.execute("UPDATE lora_settings SET is_active = 1 WHERE id = 1")
    conn.commit()

    bus = LoopbackBus()
    transport = LoopbackTransport(bus)
    scheduler = PingScheduler(conn=conn, transport=transport)
    ping_task = asyncio.create_task(scheduler.run_forever())

    try:
        result = await orchestration.sync_device_config(
            conn=conn,
            transport=transport,
            scheduler=scheduler,
            device_id="lumestrio3",
            chunk_delay_s=0.01,
            missing_check_interval_s=0.02,
            missing_reply_timeout_s=0.02,
            max_missing_checks=2,
        )
    finally:
        await _cancel(ping_task)

    assert result is False
    row = conn.execute(
        "SELECT synced_version FROM devices WHERE device_id = ?", ("lumestrio3",)
    ).fetchone()
    assert row[0] == 0  # unchanged -- stays pending for the next automatic retry


# --- run_agenda_sync_forever ----------------------------------------------


async def test_run_agenda_sync_forever_skips_relaystrio(
    db_path: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    conn = db.connect(db_path)
    _insert_device(conn, device_id="relaystrio1", device_type="relaystrio", config_version=2)
    conn.execute("UPDATE lora_settings SET is_active = 1 WHERE id = 1")
    conn.commit()
    bus = LoopbackBus()
    transport = LoopbackTransport(bus)
    scheduler = PingScheduler(conn=conn, transport=transport)

    called: list[str] = []

    async def fake_sync(*, conn, transport, scheduler, device_id):
        called.append(device_id)
        return True

    monkeypatch.setattr(orchestration, "sync_device_config", fake_sync)

    task = asyncio.create_task(
        orchestration.run_agenda_sync_forever(
            conn=conn, transport=transport, scheduler=scheduler, interval_s=0.05
        )
    )
    await asyncio.sleep(0.1)
    await _cancel(task)

    assert called == []  # relaystrio1 skipped -- not yet supported


async def test_run_agenda_sync_forever_syncs_lumestrio(
    db_path: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    conn = db.connect(db_path)
    _insert_device(conn, device_id="lumestrio3", device_type="lumestrio", config_version=2)
    conn.execute("UPDATE lora_settings SET is_active = 1 WHERE id = 1")
    conn.commit()
    bus = LoopbackBus()
    transport = LoopbackTransport(bus)
    scheduler = PingScheduler(conn=conn, transport=transport)

    called: list[str] = []

    async def fake_sync(*, conn, transport, scheduler, device_id):
        called.append(device_id)
        return True

    monkeypatch.setattr(orchestration, "sync_device_config", fake_sync)

    task = asyncio.create_task(
        orchestration.run_agenda_sync_forever(
            conn=conn, transport=transport, scheduler=scheduler, interval_s=0.05
        )
    )
    await asyncio.sleep(0.02)
    await _cancel(task)

    assert called == ["lumestrio3"]
