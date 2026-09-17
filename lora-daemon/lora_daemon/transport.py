"""COBS-framed transport over the e32.service Unix datagram socket,
ported from legacy's LoraSockIface (LoraModuleHelpers.ts). The socket
itself is a dumb byte pipe -- e32.service understands UART/radio, not
COBS or message types; framing (COBS + a single trailing 0x00 delimiter)
is purely an application-layer convention on both ends of this socket,
same as legacy.

Also provides LoopbackBus/LoopbackTransport: an in-memory stand-in with
the exact same framing, for developing and testing protocol code without
real E32 hardware (there is no dev-mode proxy in this environment, unlike
legacy's commented-out simulation block).
"""

import os
import socket

from . import cobs

DEFAULT_E32_SOCKET_PATH = "/run/e32.data"


def _split_and_decode(data: bytes) -> list[bytes]:
    """Split a chunk of wire bytes on null delimiters and COBS-decode each
    piece -- mirrors legacy's `while (buf && buf.length)` loop over
    `readUntilNull`, which tolerates multiple frames arriving concatenated
    in one read. A trailing chunk with no delimiter is discarded, matching
    legacy's "discard buffer not ended with zero" behavior.
    """
    messages = []
    while data:
        if 0 not in data:
            break
        idx = data.index(0)
        frame, data = data[:idx], data[idx + 1 :]
        if frame:  # legacy also skips the empty registration ack frame
            messages.append(cobs.decode(frame))
    return messages


class LoraSocketTransport:
    """Real transport: a Unix datagram socket talking to e32.service."""

    def __init__(
        self, *, client_socket_path: str, e32_socket_path: str = DEFAULT_E32_SOCKET_PATH
    ) -> None:
        self._client_socket_path = client_socket_path
        self._e32_socket_path = e32_socket_path
        self._sock: socket.socket | None = None

    def open(self) -> None:
        if os.path.exists(self._client_socket_path):
            os.remove(self._client_socket_path)
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        sock.bind(self._client_socket_path)
        # Empty datagram registers this client with e32.service, same as
        # legacy's initial `sock.send(Buffer.from(''), ...)`.
        sock.sendto(b"", self._e32_socket_path)
        self._sock = sock

    def close(self) -> None:
        if self._sock is not None:
            self._sock.close()
            self._sock = None
            if os.path.exists(self._client_socket_path):
                os.remove(self._client_socket_path)

    def send(self, buf: bytes) -> None:
        if self._sock is None:
            raise RuntimeError("transport not open")
        framed = cobs.encode(buf) + b"\x00"
        self._sock.sendto(framed, self._e32_socket_path)

    def receive(self, bufsize: int = 4096) -> list[bytes]:
        """Blocking receive of one datagram from e32.service, split into
        however many COBS-framed messages it contained.
        """
        if self._sock is None:
            raise RuntimeError("transport not open")
        data = self._sock.recv(bufsize)
        return _split_and_decode(data)

    def fileno(self) -> int:
        """For an event loop (asyncio add_reader, select, ...) to wait on."""
        if self._sock is None:
            raise RuntimeError("transport not open")
        return self._sock.fileno()


class LoopbackBus:
    """Shared in-memory 'radio' for tests/dev: a message sent by any
    LoopbackTransport on the bus is delivered to every *other* transport
    on the bus (never back to the sender -- no device hears its own
    transmission), framed exactly like the real socket transport so
    protocol code exercised against this is exercised against the real
    wire format too.
    """

    def __init__(self) -> None:
        self._transports: list[LoopbackTransport] = []

    def register(self, transport: LoopbackTransport) -> None:
        self._transports.append(transport)

    def broadcast(self, sender: LoopbackTransport, framed: bytes) -> None:
        for transport in self._transports:
            if transport is not sender:
                transport._inbox.append(framed)


class LoopbackTransport:
    def __init__(self, bus: LoopbackBus) -> None:
        self._bus = bus
        self._inbox: list[bytes] = []
        bus.register(self)

    def send(self, buf: bytes) -> None:
        framed = cobs.encode(buf) + b"\x00"
        self._bus.broadcast(self, framed)

    def receive_all(self) -> list[bytes]:
        messages = []
        for framed in self._inbox:
            messages.extend(_split_and_decode(framed))
        self._inbox = []
        return messages
