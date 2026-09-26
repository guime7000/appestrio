import asyncio

import pytest

from lora_daemon import daemon, db
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


async def test_run_daemon_starts_scheduler_and_stops_cleanly(db_path: str) -> None:
    conn = db.connect(db_path)
    bus = LoopbackBus()
    transport = LoopbackTransport(bus)
    stop = asyncio.Event()

    task = asyncio.create_task(daemon.run_daemon(conn=conn, transport=transport, stop=stop))
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

    task = asyncio.create_task(daemon.run_daemon(conn=conn, transport=transport, stop=stop))
    await asyncio.sleep(0.05)
    stop.set()

    # No CancelledError should escape run_daemon -- it's caught internally.
    await asyncio.wait_for(task, timeout=1.0)
