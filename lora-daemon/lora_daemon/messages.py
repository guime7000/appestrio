"""Wire message encode/decode, ported from legacy's LoraModule.ts
(`processLoraMsg` for decoding, the various `send*` methods for encoding).

Deliberately pure functions/dataclasses operating on already-COBS-decoded,
delimiter-stripped buffers -- see transport.py for the framing layer these
sit on top of. No socket, no scheduling, no DB: this module only knows how
to turn bytes into typed messages and back, so it's unit-testable with raw
buffers exactly like legacy's own commented-out dev-mode simulation block
did.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum

from .constants import BROADCAST_ADDRESS, FILE_MSG_START, MessageType

_DATE_FORMAT = "%d/%m/%Y %H:%M:%S"


class PingType(IntEnum):
    PLAIN = 0
    WITH_AGENDA_MD5 = 1
    WITH_MISSING_PARTS = 2


class MalformedMessageError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise MalformedMessageError(message)


# --- SYNC ---------------------------------------------------------------


def encode_sync(when: datetime) -> bytes:
    return bytes([MessageType.SYNC]) + when.strftime(_DATE_FORMAT).encode() + b"\x00"


def decode_sync(buf: bytes) -> str:
    _require(len(buf) >= 2, "SYNC message too short")
    end = buf.index(0, 1) if 0 in buf[1:] else len(buf)
    return buf[1:end].decode("utf-8")


# --- PING -----------------------------------------------------------------


@dataclass(frozen=True)
class Ping:
    agenda_disabled: bool
    ping_type: PingType
    disable_wifi: bool
    slot_delay_ms: int
    addresses: tuple[int, ...]

    def own_slot(self, own_address: int) -> int | None:
        try:
            return self.addresses.index(own_address)
        except ValueError:
            return None


def encode_ping(
    *,
    agenda_disabled: bool,
    ping_type: PingType,
    disable_wifi: bool,
    slot_delay_centisec: int,
    addresses: list[int],
) -> bytes:
    prelude = [int(agenda_disabled), int(ping_type), int(disable_wifi), slot_delay_centisec]
    return bytes([MessageType.PING, *prelude, *addresses])


def decode_ping(buf: bytes) -> Ping:
    _require(len(buf) >= 5, "PING message too short")
    return Ping(
        agenda_disabled=bool(buf[1]),
        ping_type=PingType(buf[2]),
        disable_wifi=bool(buf[3]),
        slot_delay_ms=buf[4] * 10,
        addresses=tuple(buf[5:]),
    )


# --- PONG -------------------------------------------------------------
#
# PONG's shape depends on which PingType the sender is expecting a reply
# to -- that context lives with whoever tracks outstanding pings (the
# scheduler, not yet built), so callers must supply it explicitly rather
# than this module guessing from the bytes alone. Mirrors legacy's own
# master-side handling, which reads `this.shouldSendAgendaInPong()`/
# `shouldSendMissingPartInPong()` (its own current mode), not the PONG
# itself, to decide how to parse it.


@dataclass(frozen=True)
class Pong:
    address: int
    active: bool
    agenda_md5: str | None = None
    missing_parts: tuple[int, ...] | None = None


def encode_pong(
    *,
    address: int,
    active: bool,
    agenda_md5: str | None = None,
    missing_parts: list[int] | None = None,
) -> bytes:
    buf = bytes([MessageType.PONG, address, int(active)])
    if agenda_md5 is not None:
        buf += agenda_md5[:8].encode() + b"\x00"
    if missing_parts is not None:
        buf += bytes(missing_parts)
    return buf


def decode_pong(
    buf: bytes, *, expect_agenda_md5: bool = False, expect_missing_parts: bool = False
) -> Pong:
    _require(len(buf) >= 3, "PONG message too short")
    address = buf[1]
    active = bool(buf[2])
    agenda_md5 = None
    missing_parts = None
    if expect_missing_parts:
        missing_parts = tuple(buf[3:])
    elif expect_agenda_md5 and len(buf) > 4:
        end = buf.index(0, 3) if 0 in buf[3:] else len(buf)
        agenda_md5 = buf[3:end].decode("utf-8")
    return Pong(address=address, active=active, agenda_md5=agenda_md5, missing_parts=missing_parts)


# --- ACTIVATE ---------------------------------------------------------


@dataclass(frozen=True)
class Activate:
    active: bool
    addresses: tuple[int, ...]

    def targets(self, own_address: int) -> bool:
        return own_address in self.addresses or BROADCAST_ADDRESS in self.addresses

    def is_multi(self) -> bool:
        # Mirrors legacy's `multiActivate = found == 255 || buf.length > 3`:
        # either an explicit broadcast, or more than one address listed.
        return BROADCAST_ADDRESS in self.addresses or len(self.addresses) > 1


def encode_activate(active: bool, addresses: list[int] | None = None) -> bytes:
    targets = addresses if addresses else [BROADCAST_ADDRESS]
    return bytes([MessageType.ACTIVATE, int(active), *targets])


def decode_activate(buf: bytes) -> Activate:
    _require(len(buf) >= 3, "ACTIVATE message too short")
    return Activate(active=bool(buf[1]), addresses=tuple(buf[2:]))


# --- DISABLE_AGENDA -----------------------------------------------------


def encode_disable_agenda(disabled: bool) -> bytes:
    return bytes([MessageType.DISABLE_AGENDA, int(disabled)])


def decode_disable_agenda(buf: bytes) -> bool:
    _require(len(buf) >= 2, "DISABLE_AGENDA message too short")
    return bool(buf[1])


# --- FILE_MSG -----------------------------------------------------------


@dataclass(frozen=True)
class FileMsgStart:
    num_parts: int
    addresses: tuple[int, ...] = field(default=())

    def targets(self, own_address: int) -> bool:
        return own_address in self.addresses or BROADCAST_ADDRESS in self.addresses


@dataclass(frozen=True)
class FileMsgChunk:
    index: int
    data: bytes


def encode_file_msg_start(num_parts: int, addresses: list[int] | None = None) -> bytes:
    targets = addresses if addresses else [BROADCAST_ADDRESS]
    return bytes([MessageType.FILE_MSG, FILE_MSG_START, num_parts, *targets])


def encode_file_msg_chunk(index: int, data: bytes) -> bytes:
    _require(0 <= index < FILE_MSG_START, "chunk index collides with FILE_MSG_START")
    return bytes([MessageType.FILE_MSG, index]) + data


def decode_file_msg(buf: bytes) -> FileMsgStart | FileMsgChunk:
    _require(len(buf) >= 2, "FILE_MSG message too short")
    msg_number = buf[1]
    if msg_number == FILE_MSG_START:
        _require(len(buf) >= 3, "FILE_MSG start frame too short")
        return FileMsgStart(num_parts=buf[2], addresses=tuple(buf[3:]))
    return FileMsgChunk(index=msg_number, data=buf[2:])


# --- generic dispatch for self-describing message types -----------------
#
# PONG is deliberately excluded -- see the note above decode_pong.

_DECODERS = {
    MessageType.SYNC: decode_sync,
    MessageType.PING: decode_ping,
    MessageType.ACTIVATE: decode_activate,
    MessageType.DISABLE_AGENDA: decode_disable_agenda,
    MessageType.FILE_MSG: decode_file_msg,
}


def decode_message(buf: bytes) -> object:
    _require(len(buf) >= 1, "empty message")
    try:
        msg_type = MessageType(buf[0])
    except ValueError as exc:
        raise MalformedMessageError(f"unknown message type byte {buf[0]}") from exc
    if msg_type == MessageType.PONG:
        raise MalformedMessageError("PONG requires decode_pong(buf, expect_...=...) directly")
    return _DECODERS[msg_type](buf)
