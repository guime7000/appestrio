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

import time

import httpx

from app.core.config import settings

DEFAULT_TIMEOUT_S = 5.0
# check_config_sync blocks on a real multi-device round trip
# (lora-daemon paces it in batches to avoid flooding the LoRa channel --
# see orchestration.check_lumestrio_config_sync), which can genuinely
# take several seconds per batch -- the default 5s budget elsewhere in
# this module isn't enough for that.
CHECK_CONFIG_SYNC_TIMEOUT_S = 30.0
# sync_device_config_and_wait polls lora-daemon's own fire-and-forget
# /devices/{id}/sync-config to completion -- a full push (chunked
# transfer + missing-parts verification, possibly several resend rounds)
# can genuinely take tens of seconds for one device.
SYNC_CONFIG_POLL_INTERVAL_S = 1.0
SYNC_CONFIG_TIMEOUT_S = 90.0


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
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> dict:
    owns_client = client is None
    http_client = client or httpx.Client(
        base_url=settings.LORA_DAEMON_URL, timeout=timeout_s
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


def sync_device_config_and_wait(
    device_id: str,
    *,
    poll_interval_s: float = SYNC_CONFIG_POLL_INTERVAL_S,
    timeout_s: float = SYNC_CONFIG_TIMEOUT_S,
    client: httpx.Client | None = None,
) -> bool:
    """Pushes `device_id`'s current desired config and blocks until
    lora-daemon reports the push finished. lora-daemon's own
    `/devices/{id}/sync-config` is fire-and-forget (202 immediately, the
    real outcome lands later in `GET /status`'s `sync_status` dict) since
    a full push+verify can take a while -- this wraps that dance into a
    plain blocking bool so callers (the "push config now" route) don't
    each reimplement the poll loop, the same way `check_config_sync`
    already hides lora-daemon's own batching/pacing behind one call.

    Returns True only if lora-daemon reports the push fully delivered
    (`state == "done"` and `success`); False if it finished unsuccessfully
    (missing parts never resolved). Raises LoraDaemonError if lora-daemon
    is unreachable or never resolves `device_id`'s status within
    `timeout_s`.
    """
    owns_client = client is None
    http_client = client or httpx.Client(base_url=settings.LORA_DAEMON_URL, timeout=DEFAULT_TIMEOUT_S)
    try:
        trigger_sync_config(device_id, client=http_client)
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            status = _request("GET", "/status", client=http_client)
            entry = status.get("sync_status", {}).get(device_id, {})
            state = entry.get("state")
            if state == "done":
                return bool(entry.get("success"))
            if state == "error":
                return False
            time.sleep(poll_interval_s)
        raise LoraDaemonError(f"sync-config for {device_id!r} timed out after {timeout_s}s")
    finally:
        if owns_client:
            http_client.close()


def check_config_sync(device_ids: list[str], *, client: httpx.Client | None = None) -> dict:
    """Blocks until lora-daemon has a real, device-confirmed answer for
    every `device_id` (or its response window elapses) -- see
    orchestration.check_lumestrio_config_sync for what "real" means here
    (a live `WITH_CONFIG_VERSION` round trip, not an inferred guess).
    Returns `{"results": {device_id: bool}}`; a `device_id` missing from
    `results` simply didn't reply in time.
    """
    return _request(
        "POST",
        "/devices/check-config-sync",
        json={"device_ids": device_ids},
        client=client,
        timeout_s=CHECK_CONFIG_SYNC_TIMEOUT_S,
    )
