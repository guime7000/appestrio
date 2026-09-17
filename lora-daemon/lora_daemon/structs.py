"""Ported from legacy's LoraStructHelpers.ts: PingableList (which devices
are currently worth pinging) and FileReceiver (FILE_MSG chunk reassembly).
Kept as plain, socket-independent state machines so they're testable
without any transport.
"""

import time


class PingableList:
    """Tracks devices that recently asked to be pinged (e.g. the frontend's
    "Test calendrier"/live-status use cases), each with a keep-alive TTL --
    ported from legacy's `keepAliveMs = 10000`.
    """

    def __init__(self, keep_alive_s: float = 10.0) -> None:
        self.keep_alive_s = keep_alive_s
        self._records: dict[int, float] = {}

    def set_pingable(self, address: int, pingable: bool) -> bool:
        """Returns True if this call started the first pingable entry
        (mirrors legacy's `isFirst` return value, used to know whether a
        currently-idle ping loop needs kicking back into life).
        """
        if not pingable:
            self._records.pop(address, None)
            return False
        is_first = len(self._records) == 0
        self._records[address] = time.monotonic()
        return is_first

    def keys(self) -> list[int]:
        return list(self._records.keys())

    def remove_old_ones(self) -> None:
        now = time.monotonic()
        stale = [k for k, t in self._records.items() if now - t > self.keep_alive_s]
        for k in stale:
            del self._records[k]


class FileReceiver:
    """FILE_MSG chunk reassembly for a single in-flight transfer. Ported
    from legacy's FileRcvT -- `expected == 0` doubles as "ignoring" (either
    "nothing started yet" or "this transfer isn't addressed to us"), same
    as legacy.
    """

    def __init__(self) -> None:
        self._parts: list[bytes | None] = []
        self.expected = 0

    def start(self, num_parts: int) -> None:
        self._parts = [None] * num_parts
        self.expected = num_parts

    def ignore(self) -> None:
        self.expected = 0

    def is_ignoring(self) -> bool:
        return self.expected == 0

    def _is_valid_state(self) -> bool:
        return self.expected != 0 and self.expected == len(self._parts)

    def has_all(self) -> bool:
        return self._is_valid_state() and all(p for p in self._parts)

    def add_part(self, index: int, chunk: bytes) -> str | None:
        if not self._is_valid_state():
            return None
        self._parts[index] = chunk
        if self.has_all():
            return self._collect()
        return None

    def _collect(self) -> str | None:
        if not self._is_valid_state():
            return None
        result = ""
        for part in self._parts:
            if not part:
                return None
            result += part.decode("utf-8")
        return result

    def missing_ids(self) -> list[int]:
        if not self._is_valid_state():
            return []
        return [i for i, part in enumerate(self._parts) if not part]

    def clean_up(self) -> None:
        self.expected = 0
