"""Thin HTTP client for `lora-daemon`'s control API (see appestrio/
lora-daemon/lora_daemon/control_api.py) -- the glue that lets `backend`
actually trigger something on the running daemon instead of only ever
updating its own DB and waiting for the daemon's next scheduled tick.

Deliberately dumb: no protocol knowledge here, just a thin wrapper over
the daemon's already-tested HTTP routes. A short-lived `httpx.Client` per
call rather than a shared pooled client -- these are infrequent,
user-triggered control-plane actions (a button click), not a hot path.

Every function accepts an optional `client` so tests can inject one built
with `httpx.MockTransport` instead of hitting a real socket.
"""

import httpx

from app.core.config import settings

DEFAULT_TIMEOUT_S = 5.0


class LoraDaemonError(Exception):
    """Raised when lora-daemon's control API can't be reached, or
    responds with an error -- callers (route handlers) should catch this
    and map it to a clean error response rather than letting a raw httpx
    exception bubble up.
    """


def _request(
    method: str,
    path: str,
    *,
    json: dict | None = None,
    client: httpx.Client | None = None,
) -> dict:
    owns_client = client is None
    http_client = client or httpx.Client(
        base_url=settings.LORA_DAEMON_URL, timeout=DEFAULT_TIMEOUT_S
    )
    try:
        response = http_client.request(method, path, json=json)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as exc:
        raise LoraDaemonError(f"{method} {path} failed: {exc}") from exc
    finally:
        if owns_client:
            http_client.close()


def trigger_clock_sync(*, client: httpx.Client | None = None) -> dict:
    return _request("POST", "/clock-sync", client=client)


def trigger_sync_config(device_id: str, *, client: httpx.Client | None = None) -> dict:
    return _request("POST", f"/devices/{device_id}/sync-config", client=client)


def send_activate(
    active: bool,
    addresses: list[int] | None = None,
    *,
    client: httpx.Client | None = None,
) -> dict:
    return _request(
        "POST", "/activate", json={"active": active, "addresses": addresses}, client=client
    )
