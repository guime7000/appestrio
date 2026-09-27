"""ACTIVATE / clock-sync / config-push orchestration.

Item 2 of the follow-up list, ported from legacy's `sendActivate`/
`sendOneClockSync`/`startAgendaSync` (LoraModule.ts). Like `scheduler.py`,
this only makes sense running on the master Pi -- an individual
endpoint's own reply-side behavior is a separate, not-yet-built piece.

Scope, and one real divergence from legacy worth flagging:

- **`lumestrio` only.** `relaystrio`'s Agenda-JSON conversion isn't built
  yet (Lora_Rewrite_Plan.md §9.9's "missing" note), so this module can't
  push anything to it -- a pending `relaystrio` device is skipped, not
  attempted, and stays pending.
- **Per-device transfers, not per-group broadcasts.** Legacy sent one
  shared agenda *file* to every device in a real Group at once -- a
  genuine airtime optimization, since every member received
  byte-identical content. This port's `config_payload` is a full
  per-device config (own name/ip/active alongside the shared calendar),
  which is not generally identical across a group's members even when
  they share a calendar -- so this pushes each pending device its own
  single-target versioned FILE_MSG transfer instead of trying to batch.
  Batching devices that happen to resolve to byte-identical payloads is a
  possible future optimization, deliberately not attempted here to avoid
  a half-correct grouping heuristic.
- **Automatic, not manually toggled.** Matches the already-decided
  automatic cyclic-sync design (§9.7): `run_agenda_sync_forever` below
  just keeps checking `db.get_pending_sync_devices` on an interval and
  pushing to whatever it finds, rather than legacy's manual
  `loraIsSyncingAgendas` toggle. A device that fails to fully sync in one
  pass simply stays pending and gets retried next cycle -- no separate
  retry-queue/backoff bookkeeping needed.
- **`send_activate`'s channel-priority handling is simplified** vs.
  legacy's `waitNoPing()`, which additionally waits out the remainder of
  the current ping interval before sending (to avoid colliding with an
  in-flight ping round). This pauses the scheduler and sends immediately
  instead, using the already-built `PingScheduler.pause()`/`resume()`
  channel-priority mechanism (§9.10's follow-up) rather than replicating
  that timing math.

Also here (added 2026-09-28, found while prepping for real hardware
testing): **`run_hex_conf_sync_forever`**, closing a gap where
`hexconf.py` (built in the initial protocol/transport port, §9.8) could
always compute the E32 module's correct radio configuration but nothing
ever actually pushed it to `/run/e32.control`. Without this, the module's
real channel/speed/FEC depended entirely on however it was last manually
configured -- silently invalidating any test if it didn't happen to match
`LoraSettings`.
"""

import asyncio
import logging
from datetime import datetime

from . import config_payload, db, hexconf, messages
from .constants import FILE_CHUNK_SIZE, MIN_CLOCK_INTERVAL_S
from .devices import address_for_device_id
from .messages import PingType
from .scheduler import PingScheduler

logger = logging.getLogger(__name__)

DEFAULT_AGENDA_SYNC_INTERVAL_S = 30.0
DEFAULT_CHUNK_DELAY_S = 1.0
DEFAULT_MISSING_CHECK_INTERVAL_S = 6.0
DEFAULT_MISSING_REPLY_TIMEOUT_S = 2.0
DEFAULT_MAX_MISSING_CHECKS = 5
DEFAULT_HEX_CONF_CHECK_INTERVAL_S = 5.0


# --- radio (hex) config sync -------------------------------------------


async def run_hex_conf_sync_forever(
    *,
    conn: object,
    transport: object,
    interval_s: float = DEFAULT_HEX_CONF_CHECK_INTERVAL_S,
) -> None:
    """Keeps the E32 module's actual radio config in sync with
    LoraSettings -- ported from legacy's `parseConf` calling `setHexConf`
    whenever the config became active (LoraModule.ts). Pushes once
    immediately on daemon startup (so a fresh start always configures the
    radio, not just on the next settings *change*), then again only when
    channel/speed/fec actually change -- avoids spamming `e32.control`
    every tick for no reason. Runs regardless of `is_active`: the radio's
    own config isn't gated on whether the daemon is pinging, matching
    legacy pushing it as soon as the config loaded, independent of the
    ping/clock-sync loops' own active checks.
    """
    last_pushed: str | None = None
    while True:
        settings = db.get_lora_settings(conn)
        hex_conf = hexconf.build_hex_conf(
            channel=settings.channel, speed=settings.speed, fec=settings.fec
        )
        if hex_conf != last_pushed:
            transport.set_hex_conf(hex_conf)
            logger.info(
                "pushed hex conf %s (channel=%s speed=%s fec=%s)",
                hex_conf,
                settings.channel,
                settings.speed,
                settings.fec,
            )
            last_pushed = hex_conf
        await asyncio.sleep(interval_s)


# --- ACTIVATE -------------------------------------------------------------


def send_activate(
    *,
    transport: object,
    scheduler: PingScheduler,
    active: bool,
    addresses: list[int] | None = None,
) -> None:
    """Broadcast or targeted ACTIVATE. Pauses the ping loop first if this
    targets more than one device (including a broadcast) -- see the
    module docstring for how this differs from legacy's `waitNoPing()`.
    Plain sync function: unlike the loops below, sending one ACTIVATE
    frame has no `await` points of its own.
    """
    is_multi = not addresses or len(addresses) > 1
    if is_multi:
        scheduler.pause()
    try:
        transport.send(messages.encode_activate(active, addresses))
    finally:
        if is_multi:
            scheduler.resume()


# --- clock sync -------------------------------------------------------------


async def run_clock_sync_forever(*, conn: object, transport: object) -> None:
    """Persistent loop, ported from scheduleNextClockSync/sendOneClockSync:
    broadcasts SYNC on LoraSettings.clock_interval_s while active. No
    manual trigger needed -- matches legacy's own master-clock behavior,
    which ran unconditionally once `isActive`/`isMasterClock`.
    """
    while True:
        settings = db.get_lora_settings(conn)
        if settings.is_active:
            transport.send(messages.encode_sync(datetime.now()))
        interval_s = max(settings.clock_interval_s, MIN_CLOCK_INTERVAL_S)
        await asyncio.sleep(interval_s)


# --- config (agenda) push, lumestrio only -----------------------------------


def _chunk(data: bytes, size: int) -> list[bytes]:
    if not data:
        return [b""]
    return [data[i : i + size] for i in range(0, len(data), size)]


async def _wait_for_missing_parts(
    scheduler: PingScheduler,
    *,
    address: int,
    device_id: str,
    reply_timeout_s: float,
) -> tuple[int, ...] | None:
    """Pings once with PingType.WITH_MISSING_PARTS and waits up to
    reply_timeout_s for that specific device's PONG. Returns its
    missing_parts, or None if no reply arrived in time. Temporarily
    installs an on_pong hook -- restored (not just cleared) afterward, in
    case something else is already using it.
    """
    result: list[tuple[int, ...] | None] = [None]
    got_reply = asyncio.Event()

    def _on_pong(identity: db.DeviceIdentity, pong: messages.Pong) -> None:
        if identity.device_id == device_id:
            result[0] = pong.missing_parts
            got_reply.set()

    previous_hook = scheduler.on_pong
    previous_ping_type = scheduler.ping_type
    scheduler.on_pong = _on_pong
    scheduler.ping_type = PingType.WITH_MISSING_PARTS
    try:
        scheduler.request_ping(address)
        try:
            await asyncio.wait_for(got_reply.wait(), timeout=reply_timeout_s)
        except TimeoutError:
            pass
        return result[0]
    finally:
        scheduler.on_pong = previous_hook
        scheduler.ping_type = previous_ping_type
        scheduler.stop_pinging(address)


async def sync_device_config(
    *,
    conn: object,
    transport: object,
    scheduler: PingScheduler,
    device_id: str,
    chunk_delay_s: float = DEFAULT_CHUNK_DELAY_S,
    missing_check_interval_s: float = DEFAULT_MISSING_CHECK_INTERVAL_S,
    missing_reply_timeout_s: float = DEFAULT_MISSING_REPLY_TIMEOUT_S,
    max_missing_checks: int = DEFAULT_MAX_MISSING_CHECKS,
) -> bool:
    """Pushes one lumestrio device's full resolved config over a single
    versioned FILE_MSG transfer, then verifies delivery via
    WITH_MISSING_PARTS pings, resending only what's missing. Returns True
    if fully delivered (and marks it synced via mark_device_synced), False
    otherwise -- an undelivered device simply stays pending
    (config_version != synced_version) and gets retried on the next call,
    per the automatic cyclic-sync design (§9.7).
    """
    config = db.resolve_device_config(conn, device_id)
    if config is None:
        logger.error("sync_device_config: unknown device_id %r", device_id)
        return False
    if config.device_type != "lumestrio":
        logger.error(
            "sync_device_config: %r is device_type=%r, not lumestrio -- "
            "relaystrio's Agenda-JSON conversion isn't built yet "
            "(Lora_Rewrite_Plan.md 9.9)",
            device_id,
            config.device_type,
        )
        return False

    address = address_for_device_id(config.device_id, config.device_type)
    body = config_payload.build_device_config_payload(config).to_json_bytes()
    chunks = _chunk(body, FILE_CHUNK_SIZE)

    scheduler.pause()
    try:
        start = messages.encode_file_msg_start_versioned(
            len(chunks), [(address, config.config_version)]
        )
        transport.send(start)
        for index, chunk in enumerate(chunks):
            await asyncio.sleep(chunk_delay_s)
            transport.send(messages.encode_file_msg_chunk(index, chunk))
    finally:
        scheduler.resume()

    missing: list[int] = list(range(len(chunks)))
    for _attempt in range(max_missing_checks):
        await asyncio.sleep(missing_check_interval_s)
        reported = await _wait_for_missing_parts(
            scheduler,
            address=address,
            device_id=device_id,
            reply_timeout_s=missing_reply_timeout_s,
        )
        if reported is None:
            logger.warning(
                "sync_device_config: %s did not respond to missing-parts ping", device_id
            )
            continue
        missing = list(reported)
        if not missing:
            break
        scheduler.pause()
        try:
            for index in missing:
                if 0 <= index < len(chunks):
                    transport.send(messages.encode_file_msg_chunk(index, chunks[index]))
                    await asyncio.sleep(chunk_delay_s)
        finally:
            scheduler.resume()

    if missing:
        logger.warning(
            "sync_device_config: %s still missing parts %s after %d checks, will retry later",
            device_id,
            missing,
            max_missing_checks,
        )
        return False

    db.mark_device_synced(conn, device_id, config.config_version)
    logger.info("sync_device_config: %s synced to version %s", device_id, config.config_version)
    return True


async def run_agenda_sync_forever(
    *,
    conn: object,
    transport: object,
    scheduler: PingScheduler,
    interval_s: float = DEFAULT_AGENDA_SYNC_INTERVAL_S,
) -> None:
    """Automatic cyclic config push: on each tick, finds every device
    whose config_version != synced_version and pushes to the lumestrio
    ones (relaystrio pending devices are skipped -- see module docstring).
    """
    while True:
        settings = db.get_lora_settings(conn)
        if settings.is_active:
            for pending in db.get_pending_sync_devices(conn):
                if pending.device_type != "lumestrio":
                    logger.debug(
                        "skipping pending %s device %s (not yet supported)",
                        pending.device_type,
                        pending.device_id,
                    )
                    continue
                await sync_device_config(
                    conn=conn, transport=transport, scheduler=scheduler, device_id=pending.device_id
                )
        await asyncio.sleep(interval_s)
