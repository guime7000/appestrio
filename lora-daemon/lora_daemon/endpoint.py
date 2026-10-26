"""lumestrio endpoint/slave mode (item 8, steps 2+3): the receive-side
counterpart to scheduler.py's master-only PingScheduler -- "I got pinged,
reply with PONG", "I got a FILE_MSG, apply it to my own local DB", "I got
an ACTIVATE, act on it". Runs unconditionally on every device (including
master, which is itself usually also a lumestrio needing to answer a
PING/ACTIVATE addressed to its own address -- legacy's own LoraModule
runs both roles in one process too), but is a pure no-op for any message
not addressed to this device's own LoRa address.

Only ever meaningful for `lumestrio` -- `relaystrio` is frozen ESP32
firmware, not this Python process -- so `own_address` here always comes
from devices.parse_device_identity_from_hostname, never from a relaystrio
hostname in practice (see daemon.py's _resolve_own_identity).

Deliberately **not** its own independent poller of the transport, unlike
PingScheduler: the transport's `receive_all()` is a destructive drain, so
two independent pollers on the same transport would race each other for
every incoming frame rather than each seeing it (found the hard way,
2026-10-26 -- a PING sent to this device's own address silently vanished
with no error, consumed by whichever of PingScheduler/EndpointResponder's
own polling loop happened to run first that tick). `handle_frame` below
is instead called by PingScheduler itself, via its `on_other_frame` hook,
for whatever it doesn't already consume as a PONG -- PingScheduler stays
the sole poller.
"""

import json
import logging
import sqlite3
from dataclasses import dataclass, field

from . import db, messages
from .messages import MessageType, PingType

logger = logging.getLogger(__name__)


@dataclass
class _IncomingTransfer:
    """Reassembly state for one in-flight FILE_MSG push addressed to us.
    `config_version` is the versioned start frame's own per-target
    version (FileMsgStartVersioned.version_for) -- the authoritative
    value applied once the transfer completes, not read back out of the
    JSON body (which also happens to carry its own copy, but the start
    frame's is what master actually intended for this specific push).
    """

    num_parts: int
    config_version: int
    chunks: dict[int, bytes] = field(default_factory=dict)

    def missing_parts(self) -> list[int]:
        return [i for i in range(self.num_parts) if i not in self.chunks]

    def is_complete(self) -> bool:
        return len(self.chunks) == self.num_parts

    def reassembled_body(self) -> bytes:
        return b"".join(self.chunks[i] for i in range(self.num_parts))


class EndpointResponder:
    """One instance per running daemon process, alongside PingScheduler.
    Owns this device's own in-flight FILE_MSG transfer (at most one at a
    time -- matches master's own "per-device transfers, not per-group
    broadcasts" design, so there's never a reason to expect two
    interleaved transfers addressed to the same device).
    """

    def __init__(
        self,
        *,
        conn: sqlite3.Connection,
        transport: object,
        own_address: int,
        own_device_type: str,
        own_device_number: int,
    ) -> None:
        self._conn = conn
        self._transport = transport
        self.own_address = own_address
        self._own_device_type = own_device_type
        self._own_device_number = own_device_number
        self._transfer: _IncomingTransfer | None = None
        self.agenda_disabled = False

    def handle_frame(self, buf: bytes) -> None:
        """Called by PingScheduler (the sole poller of the shared
        transport) via its `on_other_frame` hook, for every frame that
        isn't a PONG -- see this module's docstring for why there's no
        independent polling loop here.
        """
        if not buf:
            return
        try:
            msg_type = MessageType(buf[0])
        except ValueError:
            return
        if msg_type == MessageType.PING:
            self._handle_ping(buf)
        elif msg_type == MessageType.ACTIVATE:
            self._handle_activate(buf)
        elif msg_type == MessageType.DISABLE_AGENDA:
            self._handle_disable_agenda(buf)
        elif msg_type == MessageType.FILE_MSG:
            self._handle_file_msg(buf)
        # SYNC (clock-setting) and PONG (master-bound only, see
        # relaystrio.md: "Nodes ignore PONGs from others") are
        # deliberately not handled here yet -- SYNC needs a still-open
        # CAP_SYS_TIME-style operational answer (Lora_Daemon_To_Be_Done.md
        # §4), not just code.

    # -- PING -> PONG --------------------------------------------------

    def _handle_ping(self, buf: bytes) -> None:
        ping = messages.decode_ping(buf)
        slot = ping.own_slot(self.own_address)
        if slot is None:
            return  # not addressed to us
        # relaystrio's own firmware schedules its PONG at
        # `slot * slot_delay_ms` (relaystrio.md §3.2) -- a collision-
        # avoidance scheme for when several devices reply to one
        # broadcast PING at once. Replicating that precisely here would
        # need a real timer threaded through this synchronous dispatch
        # path; sending immediately instead is a deliberate
        # simplification, not an oversight -- it's a scheduling nicety,
        # not a correctness requirement for a single point-to-point
        # reply, and can be added later if real multi-device collisions
        # turn out to matter in practice.
        reply = self._build_pong(ping.ping_type)
        self._transport.send(reply)

    def _build_pong(self, ping_type: PingType) -> bytes:
        active = self._read_own_active()
        config_version = None
        missing_parts = None
        if ping_type == PingType.WITH_CONFIG_VERSION:
            config_version = self._read_own_config_version()
        elif ping_type == PingType.WITH_MISSING_PARTS:
            missing_parts = self._transfer.missing_parts() if self._transfer else []
        return messages.encode_pong(
            address=self.own_address,
            active=active,
            config_version=config_version,
            missing_parts=missing_parts,
        )

    def _read_own_active(self) -> bool:
        row = self._conn.execute(
            "SELECT active FROM devices WHERE device_id = ?", (self._own_device_id(),)
        ).fetchone()
        return bool(row["active"]) if row is not None else False

    def _read_own_config_version(self) -> int:
        row = self._conn.execute(
            "SELECT config_version FROM devices WHERE device_id = ?", (self._own_device_id(),)
        ).fetchone()
        return row["config_version"] if row is not None else 0

    def _own_device_id(self) -> str:
        return f"{self._own_device_type}{self._own_device_number}"

    # -- ACTIVATE --------------------------------------------------------

    def _handle_activate(self, buf: bytes) -> None:
        activate = messages.decode_activate(buf)
        if not activate.targets(self.own_address):
            return
        # Step 3 (not built yet): call backend's apply_active_state for
        # real. Logged for now so the dispatch path is observable and
        # testable ahead of that wiring -- same placeholder spirit as
        # apply_active_state itself (Docs/To_Be_Done.md item 7).
        logger.info(
            "ACTIVATE received for %s: active=%s (apply_active_state wiring: item 8 step 3, not built yet)",
            self._own_device_id(),
            activate.active,
        )

    # -- DISABLE_AGENDA ----------------------------------------------------

    def _handle_disable_agenda(self, buf: bytes) -> None:
        # No addressing at all -- implicitly global, matching SYNC
        # (Lora_Rewrite_Plan.md's wire-protocol notes). Stored for the
        # local agenda evaluator (item 7, not built yet) to consult.
        self.agenda_disabled = messages.decode_disable_agenda(buf)

    # -- FILE_MSG ----------------------------------------------------------

    def _handle_file_msg(self, buf: bytes) -> None:
        if len(buf) < 2:
            return
        if buf[1] == messages.FILE_MSG_START:
            self._handle_file_msg_start(buf)
        else:
            self._handle_file_msg_chunk(buf)

    def _handle_file_msg_start(self, buf: bytes) -> None:
        # Always the versioned shape -- only lumestrio ever targets a
        # lumestrio address, and relaystrio's plain shape would fail
        # this parse (or worse, misparse) rather than coincidentally
        # matching our own address range by chance; a malformed/
        # not-for-us frame is handled the same as a no-op either way.
        try:
            start = messages.decode_file_msg_start_versioned(buf)
        except messages.MalformedMessageError:
            return
        version = start.version_for(self.own_address)
        if version is None:
            return  # not addressed to us
        self._transfer = _IncomingTransfer(num_parts=start.num_parts, config_version=version)
        logger.info(
            "FILE_MSG start for %s: %d part(s), config_version=%d",
            self._own_device_id(),
            start.num_parts,
            version,
        )

    def _handle_file_msg_chunk(self, buf: bytes) -> None:
        if self._transfer is None:
            return  # not mid-transfer -- presumably not addressed to us
        chunk = messages.decode_file_msg(buf)
        if not isinstance(chunk, messages.FileMsgChunk):
            return
        if 0 <= chunk.index < self._transfer.num_parts:
            self._transfer.chunks[chunk.index] = chunk.data
        if self._transfer.is_complete():
            self._apply_transfer()

    def _apply_transfer(self) -> None:
        transfer = self._transfer
        self._transfer = None
        try:
            payload = json.loads(transfer.reassembled_body().decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            logger.exception(
                "FILE_MSG for %s reassembled but failed to parse as JSON -- discarding",
                self._own_device_id(),
            )
            return
        device_id = db.apply_pushed_config(
            self._conn,
            device_type=self._own_device_type,
            device_number=self._own_device_number,
            payload=payload,
        )
        logger.info(
            "applied pushed config: device_id=%s config_version=%d",
            device_id,
            transfer.config_version,
        )
