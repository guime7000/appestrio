"""Master-side PING/TDMA scheduler.

Ported from legacy's LoraModule.ts `scheduleNextPingMsg`/`sendOnePingMsg`
(lines 226-336), plus enough of the PONG half of `processLoraMsg` to close
the loop end-to-end: round-trip timing -> db.record_device_seen, the PONG
active bit -> db.reconcile_device_active.

Scope, matching the "PING/TDMA scheduler" item from Lora_Rewrite_Plan.md's
follow-up list: this is the network's *ping master* only (the device
running this daemon is "isServer"/master clock in legacy's terms) -- an
individual endpoint's own "I got pinged, reply with PONG" behavior is a
separate, much smaller piece, deferred to the orchestration work (item 2)
since it needs shouldSendAgendaInPong/shouldSendMissingPartInPong context
that only exists once startAgendaSync does. Clock sync (sendOneClockSync)
is also item 2's, not this module's.

Faithful-port decision worth flagging: legacy's periodic tick does **not**
ping every known device -- it only pings whichever devices are currently
in `pingableList`, which nothing populates automatically. In legacy, the
frontend explicitly opts a device in/out via a "keepPingingDevice"
WebSocket message (its live-status view) through `setPingableState`;
nothing else calls it. This port keeps that exact model (`request_ping`/
`stop_pinging` below) rather than silently switching to "ping everyone
every tick", which would be a real behavior change, not a straight port.
If always-on liveness for every device is wanted instead, that's a call
to make explicitly when wiring the loopback nudge channel (item 4), not
something to bake in silently here.

Channel-priority decision (2026-09-26): on the shared LoRa channel,
ACTIVATE, calendar/agenda pushes, and clock sync all outrank routine
PING/liveness traffic -- pings are the one traffic class it's fine to
delay or skip outright when something more urgent needs the airtime.
`pause()`/`resume()` below are that mechanism, ported from legacy's
`disablePing` flag (set for the duration of `startToSendNextAg`'s agenda
transfer). Item 2 (`sendActivate`/`sendOneClockSync`/`startAgendaSync`,
not built yet) is expected to call `pause()` before sending and
`resume()` after -- this scheduler doesn't decide *when* to yield the
channel, only provides the on/off switch for whoever does. Legacy's
richer `waitNoPing()` (which additionally waits out the remainder of the
current interval before an ACTIVATE, rather than just flipping a flag) is
deferred to item 2 as well, since it's specifically about ACTIVATE
timing that doesn't exist here yet.
"""

import asyncio
import logging
import select
import time
from dataclasses import dataclass

from . import db, messages
from .constants import MIN_DELAY_FOR_RESP_MS, MIN_PING_INTERVAL_S, get_num_in_ping
from .devices import address_for_device_id
from .messages import MessageType, PingType
from .structs import PingableList

logger = logging.getLogger(__name__)


def _poll_transport(transport: object) -> list[bytes]:
    """Non-blocking read of whatever frames are available right now, for
    either transport kind. Mirrors legacy's own e32ws polling loop
    (`handleLora`/`handleWs`, both non-blocking every iteration) rather
    than a true epoll/add_reader integration -- simpler, and correct here
    since PING intervals are seconds while this polls sub-second.
    """
    if hasattr(transport, "receive_all"):
        return transport.receive_all()
    ready, _, _ = select.select([transport.fileno()], [], [], 0)
    if not ready:
        return []
    return transport.receive()


@dataclass
class _PingedSlot:
    address: int
    fire_at: float  # time.monotonic() this slot's response window opens


class PingScheduler:
    """One instance per running daemon process. Owns the pingable set,
    the round-robin index across ticks, and the outstanding-slots state
    needed to match an incoming PONG back to a round-trip time.
    """

    def __init__(
        self,
        *,
        conn: object,
        transport: object,
        pingable: PingableList | None = None,
    ) -> None:
        self._conn = conn
        self._transport = transport
        self.pingable = pingable if pingable is not None else PingableList()
        self._current_ping_idx = -1
        self._slots_by_address: dict[int, _PingedSlot] = {}
        self._last_ping_type = PingType.PLAIN
        self._wake = asyncio.Event()
        self._paused = False

        # Extension points for the orchestration work (item 2) to feed
        # real values into once it exists (agenda-disabled state,
        # WITH_AGENDA_MD5/WITH_MISSING_PARTS during a sync); PLAIN and
        # not-disabled until then.
        self.agenda_disabled = False
        self.ping_type = PingType.PLAIN
        self.disable_wifi = False

    # -- external API, mirrors legacy's setPingableState -----------------

    def request_ping(self, address: int) -> bool:
        """Mark a device pingable. Returns True if the pingable set was
        empty before this call (legacy's `isFirst`). When run under
        run_forever(), that also wakes the loop immediately instead of
        waiting out the current interval -- legacy's 200ms coalescing
        setTimeout collapses here into "wake now".
        """
        is_first = self.pingable.set_pingable(address, True)
        if is_first:
            self._wake.set()
        return is_first

    def stop_pinging(self, address: int) -> None:
        self.pingable.set_pingable(address, False)

    # -- channel-priority control, mirrors legacy's `disablePing` --------

    def pause(self) -> None:
        """Suspend PING transmission so higher-priority traffic (ACTIVATE,
        agenda/calendar pushes, clock sync) gets the channel -- PONGs are
        still received and processed while paused, only sending stops.
        Idempotent; call resume() when the urgent traffic is done.
        """
        self._paused = True

    def resume(self) -> None:
        self._paused = False
        self._wake.set()  # don't wait out the rest of the current interval

    # -- one tick, ported from sendOnePingMsg -----------------------------

    def send_one_ping_round(self, ping_interval_s: int) -> None:
        """One tick: pick this round's TDMA slots from the pingable set,
        round-robining across ticks, and broadcast a single PING
        addressing all of them at once. No-ops if nothing is pingable.
        """
        self.pingable.remove_old_ones()
        addresses = self.pingable.keys()
        if not addresses:
            return
        num_in_ping = min(get_num_in_ping(ping_interval_s * 1000), len(addresses))
        if num_in_ping <= 0:
            return

        chosen: list[int] = []
        for _ in range(num_in_ping):
            self._current_ping_idx = (self._current_ping_idx + 1) % len(addresses)
            chosen.append(addresses[self._current_ping_idx])

        centisec = MIN_DELAY_FOR_RESP_MS // 10
        buf = messages.encode_ping(
            agenda_disabled=self.agenda_disabled,
            ping_type=self.ping_type,
            disable_wifi=self.disable_wifi,
            slot_delay_centisec=centisec,
            addresses=chosen,
        )
        now = time.monotonic()
        self._slots_by_address = {
            address: _PingedSlot(address=address, fire_at=now + i * (MIN_DELAY_FOR_RESP_MS / 1000))
            for i, address in enumerate(chosen)
        }
        self._last_ping_type = self.ping_type
        self._transport.send(buf)
        logger.info("sent PING to addresses %s", chosen)

    # -- receiving PONGs, ported from processLoraMsg's PONG branch -------

    def poll_incoming(self) -> None:
        """Process whatever PONGs have arrived since the last call.
        Non-blocking -- safe to call every tick of an outer event loop
        alongside send_one_ping_round.
        """
        for buf in _poll_transport(self._transport):
            self._handle_frame(buf)

    def _handle_frame(self, buf: bytes) -> None:
        if not buf or buf[0] != int(MessageType.PONG):
            return  # only PONGs are this scheduler's concern
        pong = messages.decode_pong(
            buf,
            expect_agenda_md5=self._last_ping_type == PingType.WITH_AGENDA_MD5,
            expect_missing_parts=self._last_ping_type == PingType.WITH_MISSING_PARTS,
        )
        slot = self._slots_by_address.pop(pong.address, None)
        if slot is None:
            logger.warning("PONG from unpinged/unknown address %s", pong.address)
            return
        identity = self._identity_for_address(pong.address)
        if identity is None:
            logger.error("PONG from address %s has no matching device row", pong.address)
            return
        roundtrip_ms = int((time.monotonic() - slot.fire_at) * 1000)
        db.record_device_seen(
            self._conn,
            identity.device_id,
            seen_at_iso=_now_iso(),
            roundtrip_ms=roundtrip_ms,
        )
        db.reconcile_device_active(self._conn, identity.device_id, pong.active)

    def _identity_for_address(self, address: int) -> db.DeviceIdentity | None:
        # A linear scan over every known device per PONG -- fine at the
        # device counts this system runs at (see
        # RECOMMENDED_MAX_LUMESTRIO_GROUP_SIZE in messages.py); revisit
        # with a cached address->identity map if that ever changes.
        for identity in db.list_device_identities(self._conn):
            try:
                candidate = address_for_device_id(identity.device_id, identity.device_type)
            except ValueError:
                logger.error("device_id %r doesn't parse as an address", identity.device_id)
                continue
            if candidate == address:
                return identity
        return None

    # -- persistent loop, ported from scheduleNextPingMsg's self-reschedule

    async def run_forever(self) -> None:
        """The actual persistent loop a real daemon process runs as one of
        its asyncio tasks (item 5's future entrypoint). Reads
        LoraSettings fresh every tick since `ping_interval_s`/`is_active`
        are live-editable via the backend's API. While waiting out the
        interval, keeps polling for PONGs (so replies aren't only checked
        right at the next tick) and can be woken early by request_ping or
        resume().
        """
        while True:
            settings = db.get_lora_settings(self._conn)
            if settings.is_active and not self._paused:
                self.send_one_ping_round(settings.ping_interval_s)
            interval_s = max(settings.ping_interval_s, MIN_PING_INTERVAL_S)
            self._wake.clear()
            deadline = time.monotonic() + interval_s
            while True:
                self.poll_incoming()
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                try:
                    await asyncio.wait_for(self._wake.wait(), timeout=min(remaining, 0.05))
                    break  # woken early by request_ping -- start the next tick now
                except TimeoutError:
                    continue


def _now_iso() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat()
