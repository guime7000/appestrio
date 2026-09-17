import pytest

from lora_daemon import cobs


@pytest.mark.parametrize(
    "data",
    [
        b"",
        b"\x00",
        b"a",
        b"\x00\x00\x00",
        b"hello world",
        b"\x00hello\x00world\x00",
        bytes(range(1, 255)),
        bytes(range(1, 255)) + bytes([1, 2, 3]),
        bytes(range(256)),
    ],
)
def test_round_trip(data: bytes) -> None:
    encoded = cobs.encode(data)
    assert 0 not in encoded
    assert cobs.decode(encoded) == data


def test_known_single_zero_encoding() -> None:
    # A lone zero byte encodes to two code bytes of 0x01 each (one meaning
    # "zero data bytes then an implied zero", the other terminating with
    # no implied zero since it's the last block).
    assert cobs.encode(b"\x00") == bytes([1, 1])


def test_decode_rejects_zero_code_byte() -> None:
    with pytest.raises(ValueError, match="zero byte"):
        cobs.decode(bytes([1, 0]))


def test_decode_rejects_truncated_data() -> None:
    with pytest.raises(ValueError, match="truncated"):
        cobs.decode(bytes([5, 1, 2]))
