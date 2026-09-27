"""Minimal HTTP control API for the running PingScheduler -- the loopback
nudge channel (item 4) `backend` calls into so a frontend button (e.g.
"which devices are on?", "Synchroniser les horloges") can reach the
daemon's live scheduler instance instead of waiting for its next
scheduled tick. Also serves a small hardware-test console (test_page.py)
at `GET /`, for exercising a running daemon by hand against real hardware
without needing `backend`/`frontend` at all.

Hand-rolled over asyncio streams rather than pulling in a new HTTP
dependency (aiohttp/FastAPI+uvicorn) for a handful of endpoints --
deliberately minimal: one request per connection, no keep-alive, no
chunked transfer, no routing library. If this API ever needs to grow much
past what's here, that's the signal to switch to a real framework instead
of growing this by hand.

Runs as another asyncio task in the same event loop as
PingScheduler.run_forever() (see daemon.py) -- calls into the scheduler
directly, no IPC/serialization boundary beyond the JSON request body.
Bound to localhost by default since, for now, `backend` and `lora-daemon`
run on the same Pi; widen the bind host explicitly if they're ever split
across a Compose network (item 5).
"""

import asyncio
import contextlib
import json
import logging
import sqlite3

from . import db, orchestration
from . import test_page as test_page_module
from .devices import address_for_device_id
from .scheduler import PingScheduler

logger = logging.getLogger(__name__)

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765

_REASON = {
    200: "OK",
    202: "Accepted",
    400: "Bad Request",
    404: "Not Found",
    500: "Internal Server Error",
}

_Response = tuple[int, str, bytes]


class ControlApiError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


def _json(status: int, payload: object) -> _Response:
    return status, "application/json", json.dumps(payload).encode("utf-8")


def _html(status: int, html_bytes: bytes) -> _Response:
    return status, "text/html; charset=utf-8", html_bytes


async def create_server(
    scheduler: PingScheduler,
    conn: sqlite3.Connection,
    transport: object,
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
) -> asyncio.base_events.Server:
    """Binds and returns the server without serving yet -- split out from
    serve() so tests can bind an ephemeral port (port=0) and read back
    whichever port the OS actually chose.
    """
    # One dict per server instance, shared by every connection handler --
    # tracks in-flight/finished manual `/devices/{id}/sync-config` calls
    # for the test console's status panel to poll. Not persisted anywhere;
    # purely an in-process convenience for interactive hardware testing.
    sync_status: dict[str, dict] = {}
    return await asyncio.start_server(
        lambda r, w: _handle_connection(r, w, scheduler, conn, transport, sync_status), host, port
    )


async def serve(
    scheduler: PingScheduler,
    conn: sqlite3.Connection,
    transport: object,
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
) -> None:
    server = await create_server(scheduler, conn, transport, host=host, port=port)
    addr = server.sockets[0].getsockname() if server.sockets else (host, port)
    logger.info("control API listening on %s", addr)
    async with server:
        await server.serve_forever()


async def _handle_connection(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    scheduler: PingScheduler,
    conn: sqlite3.Connection,
    transport: object,
    sync_status: dict[str, dict],
) -> None:
    status: int
    content_type: str
    body_bytes: bytes
    try:
        request_line = await reader.readline()
        if not request_line:
            writer.close()
            return
        method, path, _version = request_line.decode("latin-1").strip().split(" ", 2)

        headers: dict[str, str] = {}
        while True:
            line = await reader.readline()
            if line in (b"\r\n", b"\n", b""):
                break
            name, _, value = line.decode("latin-1").partition(":")
            headers[name.strip().lower()] = value.strip()

        length = int(headers.get("content-length") or 0)
        body = await reader.readexactly(length) if length else b""

        status, content_type, body_bytes = _dispatch(
            method, path, body, scheduler, conn, transport, sync_status
        )
    except ControlApiError as exc:
        status, content_type, body_bytes = _json(exc.status, {"error": exc.message})
    except Exception:
        logger.exception("control API request failed")
        status, content_type, body_bytes = _json(500, {"error": "internal error"})

    response = (
        f"HTTP/1.1 {status} {_REASON.get(status, 'Error')}\r\n"
        f"Content-Type: {content_type}\r\n"
        f"Content-Length: {len(body_bytes)}\r\n"
        "Connection: close\r\n\r\n"
    ).encode("latin-1") + body_bytes
    try:
        writer.write(response)
        await writer.drain()
    finally:
        writer.close()
        with contextlib.suppress(Exception):
            await writer.wait_closed()


def _dispatch(
    method: str,
    path: str,
    body: bytes,
    scheduler: PingScheduler,
    conn: sqlite3.Connection,
    transport: object,
    sync_status: dict[str, dict],
) -> _Response:
    if method == "GET" and path == "/":
        return _html(200, test_page_module.TEST_PAGE_HTML)
    if method == "GET" and path == "/health":
        return _json(200, {"ok": True})
    if method == "GET" and path == "/status":
        return _json(200, _status(scheduler, sync_status))
    if method == "GET" and path == "/devices":
        return _json(200, {"devices": _devices(conn)})
    if method == "POST" and path == "/ping-all":
        return _json(200, {"pinged": _ping_all(scheduler, conn)})
    if method == "POST" and path == "/ping-address":
        return _ping_address(body, scheduler)
    if method == "POST" and path.startswith("/devices/") and path.endswith("/ping"):
        device_id = path[len("/devices/") : -len("/ping")]
        _ping_one(scheduler, conn, device_id)
        return _json(200, {"pinged": device_id})
    if method == "POST" and path.startswith("/devices/") and path.endswith("/sync-config"):
        device_id = path[len("/devices/") : -len("/sync-config")]
        return _sync_config(device_id, scheduler, conn, transport, sync_status)
    if method == "POST" and path == "/pause":
        scheduler.pause()
        return _json(200, {"paused": True})
    if method == "POST" and path == "/resume":
        scheduler.resume()
        return _json(200, {"paused": False})
    if method == "POST" and path == "/activate":
        return _activate(body, scheduler, transport)
    raise ControlApiError(404, f"no route for {method} {path}")


def _status(scheduler: PingScheduler, sync_status: dict[str, dict]) -> dict:
    return {
        "paused": scheduler._paused,
        "pingable": scheduler.pingable.keys(),
        "last_pongs": {
            str(info.address): {
                "active": info.active,
                "agenda_md5": info.agenda_md5,
                "missing_parts": list(info.missing_parts)
                if info.missing_parts is not None
                else None,
                "roundtrip_ms": info.roundtrip_ms,
                "seen_at": info.seen_at_iso,
            }
            for info in scheduler.last_pongs.values()
        },
        "sync_status": sync_status,
    }


def _devices(conn: sqlite3.Connection) -> list[dict]:
    return [
        {
            "device_id": row.device_id,
            "device_type": row.device_type,
            "active": row.active,
            "config_version": row.config_version,
            "synced_version": row.synced_version,
            "last_seen": row.last_seen,
            "last_roundtrip_ms": row.last_roundtrip_ms,
        }
        for row in db.list_devices_status(conn)
    ]


def _ping_all(scheduler: PingScheduler, conn: sqlite3.Connection) -> int:
    count = 0
    for identity in db.list_device_identities(conn):
        try:
            address = address_for_device_id(identity.device_id, identity.device_type)
        except ValueError:
            logger.error("skipping unparseable device_id %r", identity.device_id)
            continue
        scheduler.request_ping(address)
        count += 1
    return count


def _ping_one(scheduler: PingScheduler, conn: sqlite3.Connection, device_id: str) -> None:
    identity = next(
        (i for i in db.list_device_identities(conn) if i.device_id == device_id), None
    )
    if identity is None:
        raise ControlApiError(404, f"unknown device_id {device_id!r}")
    address = address_for_device_id(identity.device_id, identity.device_type)
    scheduler.request_ping(address)


def _ping_address(body: bytes, scheduler: PingScheduler) -> _Response:
    """Pings a raw address with no DB lookup at all -- for hardware
    bring-up testing before any `devices` row exists for the target.
    """
    request = _parse_json_body(body)
    if "address" not in request:
        raise ControlApiError(400, "missing required field 'address'")
    address = request["address"]
    if not isinstance(address, int) or isinstance(address, bool):
        raise ControlApiError(400, "'address' must be an int")
    scheduler.request_ping(address)
    return _json(200, {"pinged_address": address})


def _sync_config(
    device_id: str,
    scheduler: PingScheduler,
    conn: sqlite3.Connection,
    transport: object,
    sync_status: dict[str, dict],
) -> _Response:
    """Fires the automatic config-push logic on demand for one device,
    instead of waiting for run_agenda_sync_forever's next tick -- useful
    for interactive testing. Runs as a background task since a full sync
    (chunking + missing-parts verification) can take many seconds; the
    caller polls GET /status's `sync_status` for the outcome.
    """

    async def _run() -> None:
        try:
            success = await orchestration.sync_device_config(
                conn=conn, transport=transport, scheduler=scheduler, device_id=device_id
            )
            sync_status[device_id] = {"state": "done", "success": success}
        except Exception:
            logger.exception("manual sync-config failed for %s", device_id)
            sync_status[device_id] = {"state": "error", "success": False}

    sync_status[device_id] = {"state": "running", "success": None}
    asyncio.create_task(_run())
    return _json(202, {"started": True, "device_id": device_id})


def _parse_json_body(body: bytes) -> dict:
    try:
        return json.loads(body) if body else {}
    except json.JSONDecodeError as exc:
        raise ControlApiError(400, f"invalid JSON body: {exc}") from exc


def _activate(body: bytes, scheduler: PingScheduler, transport: object) -> _Response:
    request = _parse_json_body(body)
    if "active" not in request:
        raise ControlApiError(400, "missing required field 'active'")
    addresses = request.get("addresses")
    if addresses is not None and not isinstance(addresses, list):
        raise ControlApiError(400, "'addresses' must be a list of ints if given")
    orchestration.send_activate(
        transport=transport, scheduler=scheduler, active=bool(request["active"]), addresses=addresses
    )
    return _json(200, {"active": bool(request["active"]), "addresses": addresses})
