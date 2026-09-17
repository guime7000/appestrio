"""Wire-protocol constants ported from legacy's LoraState.ts.

Two separate concepts share the byte value 255, kept as distinct named
constants deliberately (a trap called out repeatedly in
Lora_Rewrite_Plan.md §9.5/§9.7 -- conflating them into one magic literal
during the port would be an easy, hard-to-notice bug):

- BROADCAST_ADDRESS: "every device", used in ACTIVATE's and FILE_MSG's
  start-frame uuid lists.
- FILE_MSG_START: FILE_MSG's msgNumber byte meaning "this is the
  start-of-transfer frame", unrelated to addressing.
"""

from enum import IntEnum

BROADCAST_ADDRESS = 255
FILE_MSG_START = 255

# FILE_MSG data chunk size in bytes (legacy's `partSize`).
FILE_CHUNK_SIZE = 53

MIN_DELAY_FOR_RESP_MS = 500
MIN_DELAY_FOR_SEND_MS = 500
MIN_PING_INTERVAL_S = 1
MIN_CLOCK_INTERVAL_S = 1


class MessageType(IntEnum):
    SYNC = 1
    PING = 2
    PONG = 3
    ACTIVATE = 4
    DISABLE_AGENDA = 5
    FILE_MSG = 6


def get_num_in_ping(interval_ms: int) -> int:
    """How many devices fit in one PING's TDMA slot list at this interval.

    Ported from legacy's getNumInPing (LoraState.ts). Raises the same way
    legacy does when the interval is too short to fit even one slot.
    """
    interval_for_resp = interval_ms - MIN_DELAY_FOR_SEND_MS - 400
    if interval_for_resp <= 0:
        raise ValueError("invalid ping time")
    return interval_for_resp // MIN_DELAY_FOR_RESP_MS
