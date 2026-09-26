"""Minimal HTTP control API for the running PingScheduler -- the loopback
nudge channel (item 4) `backend` calls into so a frontend button (e.g.
"which devices are on?", "Synchroniser les horloges") can reach the
daemon's live scheduler instance instead of waiting for its next
scheduled tick.

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
from .devices import address_for_device_id
from .scheduler import PingScheduler

logger = logging.getLogger(__name__)

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765

_REASON = {200: "OK", 400: "Bad Request", 404: "Not Found", 500: "Internal Server Error"}


class ControlApiError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


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
    return await asyncio.start_server(
        lambda r, w: _handle_connection(r, w, scheduler, conn, transport), host, port
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
) -> None:
    status = 500
    payload: dict = {"error": "internal error"}
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

        status, payload = _dispatch(method, path, body, scheduler, conn, transport)
    except ControlApiError as exc:
        status, payload = exc.status, {"error": exc.message}
    except Exception:
        logger.exception("control API request failed")
        status, payload = 500, {"error": "internal error"}

    body_bytes = json.dumps(payload).encode("utf-8")
    response = (
        f"HTTP/1.1 {status} {_REASON.get(status, 'Error')}\r\n"
        "Content-Type: application/json\r\n"
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
) -> tuple[int, dict]:
    if method == "GET" and path == "/health":
        return 200, {"ok": True}
    if method == "POST" and path == "/ping-all":
        return 200, {"pinged": _ping_all(scheduler, conn)}
    if method == "POST" and path.startswith("/devices/") and path.endswith("/ping"):
        device_id = path[len("/devices/") : -len("/ping")]
        _ping_one(scheduler, conn, device_id)
        return 200, {"pinged": device_id}
    if method == "POST" and path == "/pause":
        scheduler.pause()
        return 200, {"paused": True}
    if method == "POST" and path == "/resume":
        scheduler.resume()
        return 200, {"paused": False}
    if method == "POST" and path == "/activate":
        return _activate(body, scheduler, transport)
    raise ControlApiError(404, f"no route for {method} {path}")


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


def _activate(body: bytes, scheduler: PingScheduler, transport: object) -> tuple[int, dict]:
    try:
        request = json.loads(body) if body else {}
    except json.JSONDecodeError as exc:
        raise ControlApiError(400, f"invalid JSON body: {exc}") from exc
    if "active" not in request:
        raise ControlApiError(400, "missing required field 'active'")
    addresses = request.get("addresses")
    if addresses is not None and not isinstance(addresses, list):
        raise ControlApiError(400, "'addresses' must be a list of ints if given")
    orchestration.send_activate(
        transport=transport, scheduler=scheduler, active=bool(request["active"]), addresses=addresses
    )
    return 200, {"active": bool(request["active"]), "addresses": addresses}
