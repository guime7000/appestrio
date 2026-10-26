import asyncio
import json

from lora_daemon import backend_client


async def _run_fake_backend(received: list[bytes]) -> tuple[asyncio.AbstractServer, int]:
    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        data = await reader.read(4096)
        received.append(data)
        writer.write(b"HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n")
        await writer.drain()
        writer.close()

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    return server, port


async def test_notify_activate_sends_expected_request() -> None:
    received: list[bytes] = []
    server, port = await _run_fake_backend(received)
    try:
        await backend_client.notify_activate(
            "lumestrio3", True, backend_url=f"http://127.0.0.1:{port}"
        )
    finally:
        server.close()

    assert len(received) == 1
    request_text = received[0].decode("ascii")
    request_line, _, rest = request_text.partition("\r\n")
    assert request_line == "POST /api/v1/devices/lumestrio3/activate HTTP/1.1"
    assert "Content-Type: application/json" in rest
    body = request_text.rsplit("\r\n\r\n", 1)[1]
    assert json.loads(body) == {"active": True}


async def test_notify_activate_does_not_raise_when_backend_unreachable() -> None:
    # Nothing listening on this port -- connection refused.
    await backend_client.notify_activate(
        "lumestrio3", False, backend_url="http://127.0.0.1:1", timeout_s=0.5
    )


async def test_notify_activate_does_not_raise_on_timeout() -> None:
    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        await reader.read(4096)
        await asyncio.Event().wait()  # never responds; cancelled below instead of timing out itself

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    try:
        await backend_client.notify_activate(
            "lumestrio3", True, backend_url=f"http://127.0.0.1:{port}", timeout_s=0.1
        )
    finally:
        server.close()
