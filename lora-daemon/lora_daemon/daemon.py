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
import sqlite3

from . import db
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
) -> None:
    """The actual run loop: starts the scheduler and blocks until told to
    stop. Decoupled from env parsing, transport lifecycle (open/close),
    and signal handling so it's directly testable -- `stop` is injectable
    for tests; main() below ties it to SIGINT/SIGTERM in production.
    """
    scheduler = PingScheduler(conn=conn, transport=transport)
    if stop is None:
        stop = asyncio.Event()

    task = asyncio.create_task(scheduler.run_forever())
    try:
        await stop.wait()
        logger.info("shutdown requested")
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


async def main() -> None:
    _setup_logging()

    db_path = _required_env("LORA_DB_PATH")
    client_socket_path = os.environ.get("LORA_CLIENT_SOCKET_PATH", DEFAULT_CLIENT_SOCKET_PATH)
    e32_socket_path = os.environ.get("LORA_E32_SOCKET_PATH", DEFAULT_E32_SOCKET_PATH)

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
        await run_daemon(conn=conn, transport=transport, stop=stop)
    finally:
        transport.close()
        conn.close()
        logger.info("shutdown complete")


def run() -> None:
    asyncio.run(main())
