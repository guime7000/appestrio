"""Entrypoint: wires the protocol/transport/DB/scheduler pieces from every
other module in this package into one running asyncio process.

This is the piece item 5 (Docker/Compose) needs to exist before it has
anything to `CMD` into, and the piece a future control API (the loopback
nudge channel, item 4) will need before it has a running `PingScheduler`
to attach to -- see Lora_Rewrite_Plan.md's follow-up list.

Configuration is env-var only (no config file), matching how `backend`'s
own `Settings` is populated -- keeps this a single small surface.
"""

import asyncio
import contextlib
import logging
import os
import signal
import socket
import sqlite3

from . import control_api, db, orchestration
from .devices import (
    LoraDeviceType,
    build_address,
    device_id_for_identity,
    parse_device_identity_from_hostname,
)
from .endpoint import EndpointResponder
from .scheduler import PingScheduler
from .transport import DEFAULT_E32_SOCKET_PATH, LoraSocketTransport

logger = logging.getLogger(__name__)

DEFAULT_CLIENT_SOCKET_PATH = "/run/lora-daemon/client.sock"


def _required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"required environment variable {name} is not set")
    return value


def _setup_logging() -> None:
    logging.basicConfig(
        level=os.environ.get("LORA_DAEMON_LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


async def run_daemon(
    *,
    conn: sqlite3.Connection,
    transport: object,
    stop: asyncio.Event | None = None,
    control_host: str = control_api.DEFAULT_HOST,
    control_port: int = control_api.DEFAULT_PORT,
    agenda_sync_interval_s: float = orchestration.DEFAULT_AGENDA_SYNC_INTERVAL_S,
    own_identity: tuple[LoraDeviceType, int] | None = None,
) -> None:
    """The actual run loop: starts the ping scheduler, clock sync, the
    automatic config-push loop, and the control API, then blocks until
    told to stop. Decoupled from env parsing, transport lifecycle
    (open/close), and signal handling so it's directly testable -- `stop`
    is injectable for tests; main() below ties it to SIGINT/SIGTERM in
    production. All of these share this one `PingScheduler` instance --
    that's the entire point of running them in-process together rather
    than as separate services.

    `own_identity` (item 8 steps 1-3) wires an EndpointResponder into
    `scheduler`'s `on_other_frame` hook -- only when this process's own
    hostname actually resolved to a (device_type, device_number), e.g. a
    master whose own hostname isn't a lumestrio endpoint simply never
    gets one, the same non-fatal spirit as _resolve_own_identity itself.
    Deliberately *not* its own asyncio task: PingScheduler is already the
    sole poller of the shared transport (see endpoint.py's module
    docstring for why a second independent poller would race it for
    every incoming frame), so the responder is purely reactive, invoked
    from inside PingScheduler's own poll.
    """
    scheduler = PingScheduler(conn=conn, transport=transport)
    if stop is None:
        stop = asyncio.Event()

    if own_identity is not None:
        own_device_type, own_device_number = own_identity
        responder = EndpointResponder(
            conn=conn,
            transport=transport,
            own_address=build_address(own_device_number, own_device_type),
            own_device_type=own_device_type.name.lower(),
            own_device_number=own_device_number,
        )
        scheduler.on_other_frame = responder.handle_frame

    tasks = [
        asyncio.create_task(scheduler.run_forever()),
        asyncio.create_task(orchestration.run_hex_conf_sync_forever(conn=conn, transport=transport)),
        asyncio.create_task(orchestration.run_clock_sync_forever(conn=conn, transport=transport)),
        asyncio.create_task(
            orchestration.run_agenda_sync_forever(
                conn=conn,
                transport=transport,
                scheduler=scheduler,
                interval_s=agenda_sync_interval_s,
            )
        ),
        asyncio.create_task(
            control_api.serve(scheduler, conn, transport, host=control_host, port=control_port)
        ),
    ]
    try:
        await stop.wait()
        logger.info("shutdown requested")
    finally:
        for task in tasks:
            task.cancel()
        for task in tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task


def _resolve_own_identity() -> tuple[LoraDeviceType, int] | None:
    """Self-identification (item 8 step 1): derives this process's own
    (device_type, device_number) from its OS hostname, for both logging
    and (since step 2/3) actually starting an EndpointResponder. Always
    non-fatal -- a master Pi's own hostname has no reason to match the
    <device_type><number> convention at all (it isn't a lumestrio
    endpoint), and this daemon ran against real relaystrio hardware
    perfectly well before this existed.
    """
    hostname = os.environ.get("LORA_HOSTNAME") or socket.gethostname()
    try:
        identity = parse_device_identity_from_hostname(hostname)
    except ValueError:
        logger.info(
            "own hostname %r doesn't match <device_type><number> -- "
            "not a lumestrio endpoint, or self-identification not applicable here",
            hostname,
        )
        return None
    device_type, device_number = identity
    device_id = device_id_for_identity(device_type, device_number)
    logger.info("own identity: hostname=%r -> device_id=%s", hostname, device_id)
    return identity


async def main() -> None:
    _setup_logging()
    own_identity = _resolve_own_identity()

    db_path = _required_env("LORA_DB_PATH")
    client_socket_path = os.environ.get("LORA_CLIENT_SOCKET_PATH", DEFAULT_CLIENT_SOCKET_PATH)
    e32_socket_path = os.environ.get("LORA_E32_SOCKET_PATH", DEFAULT_E32_SOCKET_PATH)
    control_host = os.environ.get("LORA_CONTROL_HOST", control_api.DEFAULT_HOST)
    control_port = int(os.environ.get("LORA_CONTROL_PORT", control_api.DEFAULT_PORT))

    conn = db.connect(db_path)
    transport = LoraSocketTransport(
        client_socket_path=client_socket_path, e32_socket_path=e32_socket_path
    )
    transport.open()
    logger.info("transport open: client=%s e32=%s", client_socket_path, e32_socket_path)

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)

    try:
        await run_daemon(
            conn=conn,
            transport=transport,
            stop=stop,
            control_host=control_host,
            control_port=control_port,
            own_identity=own_identity,
        )
    finally:
        transport.close()
        conn.close()
        logger.info("shutdown complete")


def run() -> None:
    asyncio.run(main())
