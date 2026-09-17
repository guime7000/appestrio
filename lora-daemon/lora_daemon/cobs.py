"""Consistent Overhead Byte Stuffing (COBS).

Ported from the npm `cobs` package's semantics as used by legacy's
LoraModuleHelpers.ts (`sendBufToLora`/`setServiceRunning`): `encode()`
never touches the framing delimiter itself -- callers append/strip the
single trailing 0x00 byte that terminates a datagram on the wire (see
transport.py). This module only turns arbitrary bytes into a
zero-byte-free representation and back.
"""

MAX_BLOCK_SIZE = 254


def encode(data: bytes) -> bytes:
    output = bytearray([0])  # placeholder for the first block's code byte
    code_idx = 0
    code = 1

    def finish_block() -> None:
        nonlocal code
        output[code_idx] = code
        code = 1

    for byte in data:
        if byte == 0:
            finish_block()
            output.append(0)  # placeholder for the next block's code byte
            code_idx = len(output) - 1
        else:
            output.append(byte)
            code += 1
            if code == 0xFF:
                finish_block()
                output.append(0)
                code_idx = len(output) - 1

    finish_block()
    return bytes(output)


def decode(data: bytes) -> bytes:
    output = bytearray()
    idx = 0
    n = len(data)
    while idx < n:
        code = data[idx]
        if code == 0:
            raise ValueError("zero byte found in COBS-encoded data")
        idx += 1
        end = idx + code - 1
        if end > n:
            raise ValueError("COBS-encoded data is truncated")
        output.extend(data[idx:end])
        idx = end
        if code < 0xFF and idx < n:
            output.append(0)
    return bytes(output)


def _self_test() -> None:
    cases = [
        b"",
        b"\x00",
        b"\x00\x00",
        b"hello",
        b"\x00hello\x00world\x00",
        bytes(range(1, 255)),  # exactly one max-length non-zero run
        bytes(range(1, 255)) + bytes([1, 2, 3]),  # forces a 0xFF continuation
    ]
    for original in cases:
        encoded = encode(original)
        assert 0 not in encoded, f"encoded output contains a zero byte: {encoded!r}"
        decoded = decode(encoded)
        assert decoded == original, f"round-trip failed for {original!r}: got {decoded!r}"


_self_test()
