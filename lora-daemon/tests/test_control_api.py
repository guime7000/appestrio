import asyncio
import contextlib
import json

from lora_daemon import control_api, db, messages
from lora_daemon.devices import LoraDeviceType, build_address
from lora_daemon.scheduler import PingScheduler
from lora_daemon.transport import LoopbackBus, LoopbackTransport

LUMESTRIO_3_ADDRESS = build_address(3, LoraDeviceType.LUMESTRIO)
RELAYSTRIO_1_ADDRESS = build_address(1, LoraDeviceType.RELAYSTRIO)


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


async def _start(scheduler, conn, transport):
    server = await control_api.create_server(scheduler, conn, transport, host="127.0.0.1", port=0)
    host, port = server.sockets[0].getsockname()
    serve_task = asyncio.create_task(server.serve_forever())
    return server, serve_task, host, port


async def _stop(server, serve_task) -> None:
    server.close()
    await server.wait_closed()
    serve_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await serve_task


async def _request(host: str, port: int, method: str, path: str, body: bytes = b""):
    reader, writer = await asyncio.open_connection(host, port)
    request = (
        f"{method} {path} HTTP/1.1\r\n"
        f"Host: {host}\r\n"
        f"Content-Length: {len(body)}\r\n"
        "Connection: close\r\n\r\n"
    ).encode("latin-1") + body
    writer.write(request)
    await writer.drain()

    status_line = await reader.readline()
    status = int(status_line.decode("latin-1").split(" ")[1])

    headers = {}
    while True:
        line = await reader.readline()
        if line in (b"\r\n", b"\n", b""):
            break
        name, _, value = line.decode("latin-1").partition(":")
        headers[name.strip().lower()] = value.strip()

    length = int(headers.get("content-length") or 0)
    raw_body = await reader.readexactly(length) if length else b""
    writer.close()
    await writer.wait_closed()
    payload = json.loads(raw_body) if raw_body else None
    return status, payload


async def _request_raw(host: str, port: int, method: str, path: str):
    """Like _request, but returns (status, content_type, raw_bytes)
    without assuming a JSON body -- for routes like GET / that serve
    HTML.
    """
    reader, writer = await asyncio.open_connection(host, port)
    request = f"{method} {path} HTTP/1.1\r\nHost: {host}\r\nConnection: close\r\n\r\n".encode("latin-1")
    writer.write(request)
    await writer.drain()

    status_line = await reader.readline()
    status = int(status_line.decode("latin-1").split(" ")[1])

    headers = {}
    while True:
        line = await reader.readline()
        if line in (b"\r\n", b"\n", b""):
            break
        name, _, value = line.decode("latin-1").partition(":")
        headers[name.strip().lower()] = value.strip()

    length = int(headers.get("content-length") or 0)
    raw_body = await reader.readexactly(length) if length else b""
    writer.close()
    await writer.wait_closed()
    return status, headers.get("content-type", ""), raw_body


async def test_health(db_path: str) -> None:
    conn = db.connect(db_path)
    bus = LoopbackBus()
    transport = LoopbackTransport(bus)
    scheduler = PingScheduler(conn=conn, transport=transport)
    server, serve_task, host, port = await _start(scheduler, conn, transport)
    try:
        status, payload = await _request(host, port, "GET", "/health")
        assert status == 200
        assert payload == {"ok": True}
    finally:
        await _stop(server, serve_task)


async def test_ping_all_marks_every_known_device_pingable(db_path: str) -> None:
    conn = db.connect(db_path)
    _insert_device(conn, device_id="lumestrio3", device_type="lumestrio")
    _insert_device(conn, uuid="dev-uuid-2", device_id="relaystrio1", device_type="relaystrio")
    bus = LoopbackBus()
    transport = LoopbackTransport(bus)
    scheduler = PingScheduler(conn=conn, transport=transport)
    server, serve_task, host, port = await _start(scheduler, conn, transport)
    try:
        status, payload = await _request(host, port, "POST", "/ping-all")
        assert status == 200
        assert payload == {"pinged": 2}
        assert set(scheduler.pingable.keys()) == {LUMESTRIO_3_ADDRESS, RELAYSTRIO_1_ADDRESS}
    finally:
        await _stop(server, serve_task)


async def test_ping_one_device(db_path: str) -> None:
    conn = db.connect(db_path)
    _insert_device(conn)
    bus = LoopbackBus()
    transport = LoopbackTransport(bus)
    scheduler = PingScheduler(conn=conn, transport=transport)
    server, serve_task, host, port = await _start(scheduler, conn, transport)
    try:
        status, payload = await _request(host, port, "POST", "/devices/lumestrio3/ping")
        assert status == 200
        assert payload == {"pinged": "lumestrio3"}
        assert scheduler.pingable.keys() == [LUMESTRIO_3_ADDRESS]
    finally:
        await _stop(server, serve_task)


async def test_ping_one_unknown_device_returns_404(db_path: str) -> None:
    conn = db.connect(db_path)
    bus = LoopbackBus()
    transport = LoopbackTransport(bus)
    scheduler = PingScheduler(conn=conn, transport=transport)
    server, serve_task, host, port = await _start(scheduler, conn, transport)
    try:
        status, payload = await _request(host, port, "POST", "/devices/nosuchdevice/ping")
        assert status == 404
        assert "nosuchdevice" in payload["error"]
    finally:
        await _stop(server, serve_task)


async def test_pause_and_resume(db_path: str) -> None:
    conn = db.connect(db_path)
    bus = LoopbackBus()
    transport = LoopbackTransport(bus)
    scheduler = PingScheduler(conn=conn, transport=transport)
    server, serve_task, host, port = await _start(scheduler, conn, transport)
    try:
        status, payload = await _request(host, port, "POST", "/pause")
        assert (status, payload) == (200, {"paused": True})
        assert scheduler._paused is True

        status, payload = await _request(host, port, "POST", "/resume")
        assert (status, payload) == (200, {"paused": False})
        assert scheduler._paused is False
    finally:
        await _stop(server, serve_task)


async def test_activate_broadcast(db_path: str) -> None:
    conn = db.connect(db_path)
    bus = LoopbackBus()
    transport = LoopbackTransport(bus)
    listener = LoopbackTransport(bus)
    scheduler = PingScheduler(conn=conn, transport=transport)
    server, serve_task, host, port = await _start(scheduler, conn, transport)
    try:
        status, payload = await _request(
            host, port, "POST", "/activate", json.dumps({"active": True}).encode()
        )
        assert status == 200
        assert payload == {"active": True, "addresses": None}
        [frame] = listener.receive_all()
        activate = messages.decode_activate(frame)
        assert activate.active is True
        assert activate.addresses == (messages.BROADCAST_ADDRESS,)
    finally:
        await _stop(server, serve_task)


async def test_activate_targeted(db_path: str) -> None:
    conn = db.connect(db_path)
    bus = LoopbackBus()
    transport = LoopbackTransport(bus)
    listener = LoopbackTransport(bus)
    scheduler = PingScheduler(conn=conn, transport=transport)
    server, serve_task, host, port = await _start(scheduler, conn, transport)
    try:
        status, payload = await _request(
            host,
            port,
            "POST",
            "/activate",
            json.dumps({"active": False, "addresses": [3]}).encode(),
        )
        assert status == 200
        assert payload == {"active": False, "addresses": [3]}
        [frame] = listener.receive_all()
        activate = messages.decode_activate(frame)
        assert activate.active is False
        assert activate.addresses == (3,)
    finally:
        await _stop(server, serve_task)


async def test_activate_missing_field_returns_400(db_path: str) -> None:
    conn = db.connect(db_path)
    bus = LoopbackBus()
    transport = LoopbackTransport(bus)
    scheduler = PingScheduler(conn=conn, transport=transport)
    server, serve_task, host, port = await _start(scheduler, conn, transport)
    try:
        status, payload = await _request(host, port, "POST", "/activate", b"{}")
        assert status == 400
        assert "active" in payload["error"]
    finally:
        await _stop(server, serve_task)


async def test_unknown_route_returns_404(db_path: str) -> None:
    conn = db.connect(db_path)
    bus = LoopbackBus()
    transport = LoopbackTransport(bus)
    scheduler = PingScheduler(conn=conn, transport=transport)
    server, serve_task, host, port = await _start(scheduler, conn, transport)
    try:
        status, _payload = await _request(host, port, "GET", "/nope")
        assert status == 404
    finally:
        await _stop(server, serve_task)


async def test_root_serves_the_test_console_html(db_path: str) -> None:
    conn = db.connect(db_path)
    bus = LoopbackBus()
    transport = LoopbackTransport(bus)
    scheduler = PingScheduler(conn=conn, transport=transport)
    server, serve_task, host, port = await _start(scheduler, conn, transport)
    try:
        status, content_type, body = await _request_raw(host, port, "GET", "/")
        assert status == 200
        assert content_type.startswith("text/html")
        assert b"lora-daemon test console" in body
    finally:
        await _stop(server, serve_task)


async def test_ping_address_marks_pingable_without_a_db_row(db_path: str) -> None:
    conn = db.connect(db_path)
    bus = LoopbackBus()
    transport = LoopbackTransport(bus)
    scheduler = PingScheduler(conn=conn, transport=transport)
    server, serve_task, host, port = await _start(scheduler, conn, transport)
    try:
        status, payload = await _request(
            host, port, "POST", "/ping-address", json.dumps({"address": 42}).encode()
        )
        assert status == 200
        assert payload == {"pinged_address": 42}
        assert scheduler.pingable.keys() == [42]
    finally:
        await _stop(server, serve_task)


async def test_ping_address_rejects_non_int(db_path: str) -> None:
    conn = db.connect(db_path)
    bus = LoopbackBus()
    transport = LoopbackTransport(bus)
    scheduler = PingScheduler(conn=conn, transport=transport)
    server, serve_task, host, port = await _start(scheduler, conn, transport)
    try:
        status, payload = await _request(
            host, port, "POST", "/ping-address", json.dumps({"address": "abc"}).encode()
        )
        assert status == 400
        assert "int" in payload["error"]
    finally:
        await _stop(server, serve_task)


async def test_status_reports_paused_pingable_and_last_pongs(db_path: str) -> None:
    conn = db.connect(db_path)
    bus = LoopbackBus()
    transport = LoopbackTransport(bus)
    device = LoopbackTransport(bus)
    scheduler = PingScheduler(conn=conn, transport=transport)
    scheduler.request_ping(LUMESTRIO_3_ADDRESS)
    scheduler.send_one_ping_round(ping_interval_s=5)
    device.receive_all()
    device.send(messages.encode_pong(address=LUMESTRIO_3_ADDRESS, active=True))
    scheduler.poll_incoming()

    server, serve_task, host, port = await _start(scheduler, conn, transport)
    try:
        status, payload = await _request(host, port, "GET", "/status")
        assert status == 200
        assert payload["paused"] is False
        assert payload["pingable"] == [LUMESTRIO_3_ADDRESS]
        pong = payload["last_pongs"][str(LUMESTRIO_3_ADDRESS)]
        assert pong["active"] is True
        assert pong["roundtrip_ms"] >= 0
    finally:
        await _stop(server, serve_task)


async def test_devices_lists_db_status(db_path: str) -> None:
    conn = db.connect(db_path)
    _insert_device(conn, config_version=3, synced_version=1)
    bus = LoopbackBus()
    transport = LoopbackTransport(bus)
    scheduler = PingScheduler(conn=conn, transport=transport)
    server, serve_task, host, port = await _start(scheduler, conn, transport)
    try:
        status, payload = await _request(host, port, "GET", "/devices")
        assert status == 200
        [device] = payload["devices"]
        assert device["device_id"] == "lumestrio3"
        assert device["config_version"] == 3
        assert device["synced_version"] == 1
    finally:
        await _stop(server, serve_task)


async def test_sync_config_starts_background_task_and_reports_status(db_path: str) -> None:
    conn = db.connect(db_path)
    _insert_device(conn, config_version=1, synced_version=0)
    conn.execute("UPDATE lora_settings SET is_active = 1 WHERE id = 1")
    conn.commit()
    bus = LoopbackBus()
    transport = LoopbackTransport(bus)
    scheduler = PingScheduler(conn=conn, transport=transport)
    server, serve_task, host, port = await _start(scheduler, conn, transport)
    try:
        status, payload = await _request(
            host, port, "POST", "/devices/lumestrio3/sync-config"
        )
        assert status == 202
        assert payload == {"started": True, "device_id": "lumestrio3"}

        status, payload = await _request(host, port, "GET", "/status")
        assert payload["sync_status"]["lumestrio3"]["state"] in ("running", "done", "error")
    finally:
        await _stop(server, serve_task)
