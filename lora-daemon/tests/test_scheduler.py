import asyncio

import pytest

from lora_daemon import db
from lora_daemon import scheduler as sched_mod
from lora_daemon.devices import LoraDeviceType, build_address
from lora_daemon.messages import PingType, decode_ping, encode_pong
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


def test_send_one_ping_round_noop_when_nothing_pingable(db_path: str) -> None:
    conn = db.connect(db_path)
    bus = LoopbackBus()
    transport = LoopbackTransport(bus)
    listener = LoopbackTransport(bus)
    scheduler = sched_mod.PingScheduler(conn=conn, transport=transport)

    scheduler.send_one_ping_round(ping_interval_s=5)

    assert listener.receive_all() == []


def test_send_one_ping_round_pings_pingable_addresses(db_path: str) -> None:
    conn = db.connect(db_path)
    bus = LoopbackBus()
    transport = LoopbackTransport(bus)
    listener = LoopbackTransport(bus)
    scheduler = sched_mod.PingScheduler(conn=conn, transport=transport)
    scheduler.request_ping(LUMESTRIO_3_ADDRESS)

    scheduler.send_one_ping_round(ping_interval_s=5)

    [frame] = listener.receive_all()
    ping = decode_ping(frame)
    assert ping.addresses == (LUMESTRIO_3_ADDRESS,)
    assert ping.ping_type == PingType.PLAIN


def test_send_one_ping_round_round_robins_across_ticks(db_path: str) -> None:
    conn = db.connect(db_path)
    bus = LoopbackBus()
    transport = LoopbackTransport(bus)
    listener = LoopbackTransport(bus)
    scheduler = sched_mod.PingScheduler(conn=conn, transport=transport)
    for address in (10, 20, 30):
        scheduler.request_ping(address)

    # get_num_in_ping(2000) == 2: only 2 of the 3 pingable addresses fit
    # in one PING, so consecutive ticks must round-robin through them.
    scheduler.send_one_ping_round(ping_interval_s=2)
    first_round = decode_ping(listener.receive_all()[0]).addresses

    scheduler.send_one_ping_round(ping_interval_s=2)
    second_round = decode_ping(listener.receive_all()[0]).addresses

    assert first_round == (10, 20)
    assert second_round == (30, 10)


def test_poll_incoming_records_pong(db_path: str) -> None:
    conn = db.connect(db_path)
    _insert_device(conn)
    bus = LoopbackBus()
    transport = LoopbackTransport(bus)
    device = LoopbackTransport(bus)
    scheduler = sched_mod.PingScheduler(conn=conn, transport=transport)
    scheduler.request_ping(LUMESTRIO_3_ADDRESS)

    scheduler.send_one_ping_round(ping_interval_s=5)
    device.receive_all()  # drain the PING itself, not under test here
    device.send(encode_pong(address=LUMESTRIO_3_ADDRESS, active=True))

    scheduler.poll_incoming()

    row = conn.execute(
        "SELECT active, last_seen, last_roundtrip_ms FROM devices WHERE device_id = ?",
        ("lumestrio3",),
    ).fetchone()
    assert row["active"] == 1
    assert row["last_seen"] is not None
    assert row["last_roundtrip_ms"] is not None


def test_poll_incoming_ignores_pong_from_unpinged_address(db_path: str) -> None:
    conn = db.connect(db_path)
    _insert_device(conn)
    bus = LoopbackBus()
    transport = LoopbackTransport(bus)
    device = LoopbackTransport(bus)
    scheduler = sched_mod.PingScheduler(conn=conn, transport=transport)

    device.send(encode_pong(address=LUMESTRIO_3_ADDRESS, active=True))
    scheduler.poll_incoming()

    row = conn.execute(
        "SELECT last_seen FROM devices WHERE device_id = ?", ("lumestrio3",)
    ).fetchone()
    assert row["last_seen"] is None


def test_poll_incoming_records_last_pongs_even_without_a_db_row(db_path: str) -> None:
    # No _insert_device call here -- this is the raw-address hardware
    # testing case (the test console's "ping address" button), where the
    # daemon knows nothing about who it's pinging yet.
    conn = db.connect(db_path)
    bus = LoopbackBus()
    transport = LoopbackTransport(bus)
    device = LoopbackTransport(bus)
    scheduler = sched_mod.PingScheduler(conn=conn, transport=transport)
    scheduler.request_ping(LUMESTRIO_3_ADDRESS)

    scheduler.send_one_ping_round(ping_interval_s=5)
    device.receive_all()
    device.send(encode_pong(address=LUMESTRIO_3_ADDRESS, active=True))

    scheduler.poll_incoming()

    info = scheduler.last_pongs[LUMESTRIO_3_ADDRESS]
    assert info.active is True
    assert info.roundtrip_ms >= 0
    assert info.seen_at_iso


def test_pause_and_resume_toggle_paused_state(db_path: str) -> None:
    conn = db.connect(db_path)
    bus = LoopbackBus()
    transport = LoopbackTransport(bus)
    scheduler = sched_mod.PingScheduler(conn=conn, transport=transport)

    assert scheduler._paused is False
    scheduler.pause()
    assert scheduler._paused is True
    scheduler.resume()
    assert scheduler._paused is False


async def test_run_forever_sends_first_round_immediately(db_path: str) -> None:
    conn = db.connect(db_path)
    conn.execute("UPDATE lora_settings SET is_active = 1, ping_interval_s = 5 WHERE id = 1")
    conn.commit()
    bus = LoopbackBus()
    transport = LoopbackTransport(bus)
    listener = LoopbackTransport(bus)
    scheduler = sched_mod.PingScheduler(conn=conn, transport=transport)
    scheduler.request_ping(LUMESTRIO_3_ADDRESS)

    task = asyncio.create_task(scheduler.run_forever())
    await asyncio.sleep(0.1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    frames = listener.receive_all()
    assert len(frames) == 1
    assert decode_ping(frames[0]).addresses == (LUMESTRIO_3_ADDRESS,)


async def test_run_forever_wakes_early_on_request_ping(db_path: str) -> None:
    conn = db.connect(db_path)
    conn.execute("UPDATE lora_settings SET is_active = 1, ping_interval_s = 100 WHERE id = 1")
    conn.commit()
    bus = LoopbackBus()
    transport = LoopbackTransport(bus)
    listener = LoopbackTransport(bus)
    scheduler = sched_mod.PingScheduler(conn=conn, transport=transport)

    task = asyncio.create_task(scheduler.run_forever())
    await asyncio.sleep(0.05)
    assert listener.receive_all() == []  # nothing pingable yet -- first tick was a no-op

    scheduler.request_ping(LUMESTRIO_3_ADDRESS)
    await asyncio.sleep(0.15)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    frames = listener.receive_all()
    assert len(frames) == 1
    assert decode_ping(frames[0]).addresses == (LUMESTRIO_3_ADDRESS,)


async def test_run_forever_skips_ping_while_paused(db_path: str) -> None:
    conn = db.connect(db_path)
    conn.execute("UPDATE lora_settings SET is_active = 1, ping_interval_s = 5 WHERE id = 1")
    conn.commit()
    bus = LoopbackBus()
    transport = LoopbackTransport(bus)
    listener = LoopbackTransport(bus)
    scheduler = sched_mod.PingScheduler(conn=conn, transport=transport)
    scheduler.request_ping(LUMESTRIO_3_ADDRESS)
    scheduler.pause()

    task = asyncio.create_task(scheduler.run_forever())
    await asyncio.sleep(0.1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert listener.receive_all() == []


async def test_run_forever_resume_wakes_and_sends(db_path: str) -> None:
    conn = db.connect(db_path)
    conn.execute("UPDATE lora_settings SET is_active = 1, ping_interval_s = 100 WHERE id = 1")
    conn.commit()
    bus = LoopbackBus()
    transport = LoopbackTransport(bus)
    listener = LoopbackTransport(bus)
    scheduler = sched_mod.PingScheduler(conn=conn, transport=transport)
    scheduler.request_ping(LUMESTRIO_3_ADDRESS)
    scheduler.pause()

    task = asyncio.create_task(scheduler.run_forever())
    await asyncio.sleep(0.05)
    assert listener.receive_all() == []  # paused -- first tick sent nothing

    scheduler.resume()
    await asyncio.sleep(0.15)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    frames = listener.receive_all()
    assert len(frames) == 1
    assert decode_ping(frames[0]).addresses == (LUMESTRIO_3_ADDRESS,)


async def test_run_forever_skips_ping_when_settings_inactive(db_path: str) -> None:
    conn = db.connect(db_path)
    # lora_settings.is_active defaults to 0/False in the fixture.
    bus = LoopbackBus()
    transport = LoopbackTransport(bus)
    listener = LoopbackTransport(bus)
    scheduler = sched_mod.PingScheduler(conn=conn, transport=transport)
    scheduler.request_ping(LUMESTRIO_3_ADDRESS)

    task = asyncio.create_task(scheduler.run_forever())
    await asyncio.sleep(0.1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert listener.receive_all() == []
