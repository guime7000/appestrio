"""Thin outbound HTTP client lora-daemon uses to call back into this
device's own `backend` -- the reverse half of the control-plane channel
(the only other HTTP wiring so far, app/services/lora_daemon_client.py in
`backend`, goes the other way: `backend` -> `lora-daemon`). Needed for
item 8 step 3: when an ACTIVATE frame addressed to our own address
arrives, the actual physical effect (OSC/mpv/relay -- apply_active_state)
lives in `backend`, not here, so this device's own `backend` instance has
to be told.

Hand-rolled over asyncio streams rather than pulling in a new HTTP
dependency, matching control_api.py's own reasoning for staying
dependency-free: one POST, no routing, no connection reuse, no response
body to parse. Best-effort and non-fatal -- a slave whose local `backend`
container isn't reachable yet (startup ordering, a crash) must not take
down EndpointResponder's whole dispatch path over it; the state write
that actually matters for the next PONG (db.reconcile_device_active)
already happened before this is ever called.
"""

import asyncio
import contextlib
import json
import logging
from urllib.parse import urlsplit

logger = logging.getLogger(__name__)

DEFAULT_BACKEND_URL = "http://backend:8000"
DEFAULT_API_PREFIX = "/api/v1"
DEFAULT_TIMEOUT_S = 5.0


async def _post_json(
    path: str,
    body: dict,
    *,
    backend_url: str,
    timeout_s: float,
    description: str,
) -> None:
    """Shared POST plumbing for every reverse-channel call -- a single
    hand-rolled request/response exchange, logging and swallowing any
    failure instead of raising (see this module's docstring for why).
    `description` is just for the log lines (e.g. "ACTIVATE for
    lumestrio3").
    """
    parts = urlsplit(backend_url)
    port = parts.port or (443 if parts.scheme == "https" else 80)
    encoded_body = json.dumps(body).encode("utf-8")
    request = (
        f"POST {path} HTTP/1.1\r\n"
        f"Host: {parts.hostname}\r\n"
        "Content-Type: application/json\r\n"
        f"Content-Length: {len(encoded_body)}\r\n"
        "Connection: close\r\n"
        "\r\n"
    ).encode("ascii") + encoded_body

    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(parts.hostname, port), timeout=timeout_s
        )
    except (OSError, TimeoutError) as exc:
        logger.warning("couldn't reach backend to notify %s: %s", description, exc)
        return

    try:
        writer.write(request)
        await writer.drain()
        status_line = await asyncio.wait_for(reader.readline(), timeout=timeout_s)
        logger.info(
            "notified backend of %s -> %s",
            description,
            status_line.decode("ascii", "replace").strip(),
        )
    except (OSError, TimeoutError) as exc:
        logger.warning("backend notification for %s failed mid-request: %s", description, exc)
    finally:
        writer.close()
        with contextlib.suppress(OSError):
            await writer.wait_closed()


async def notify_activate(
    device_id: str,
    active: bool,
    *,
    backend_url: str = DEFAULT_BACKEND_URL,
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> None:
    """POSTs {"active": active} to backend's `/api/v1/devices/{device_id}
    /activate` so it can run `apply_active_state`.
    """
    await _post_json(
        f"{DEFAULT_API_PREFIX}/devices/{device_id}/activate",
        {"active": active},
        backend_url=backend_url,
        timeout_s=timeout_s,
        description=f"ACTIVATE for {device_id} (active={active})",
    )


async def notify_agenda_disabled(
    disabled: bool,
    *,
    backend_url: str = DEFAULT_BACKEND_URL,
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> None:
    """POSTs {"disabled": disabled} to backend's `/api/v1/agenda/disabled`
    so item 7's local evaluator knows to pause/resume -- the agenda-
    disabled flag crosses from `lora-daemon` (which receives it over
    LoRa) to `backend` (which evaluates it) this way, kept purely
    in-memory on the `backend` side (never persisted -- see
    app/services/agenda_evaluator.py's docstring).
    """
    await _post_json(
        f"{DEFAULT_API_PREFIX}/agenda/disabled",
        {"disabled": disabled},
        backend_url=backend_url,
        timeout_s=timeout_s,
        description=f"agenda disabled={disabled}",
    )
