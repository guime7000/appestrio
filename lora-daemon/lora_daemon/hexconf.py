"""E32 radio hex-configuration bit-twiddling, ported verbatim from
LoraModuleHelpers.ts's buildHexConfFromState (including its exact
bit-indexing scheme -- this writes directly to the radio hardware via
`/run/e32.control`, so byte-for-byte fidelity with legacy matters more
than code cleanliness here).

Known inherited quirk, not fixed here: the string-based bit-twiddling
(`_dec_to_bin`'s `align_mod=4` padding) only reliably produces a full
8-bit string because the untouched high bits of the channel/speed byte
happen to be non-zero for the *default* config (checked by the self-test
below). A channel value whose low 6 bits transiently zero the whole byte
mid-computation (e.g. channel=0, since byte 4's untouched bits 6-7 are
also 0) would hit the same edge case legacy's own implementation has --
replicated as-is rather than silently "fixed", since this daemon must
stay wire/hardware-compatible with whatever legacy actually produced for
a given input, bug or not.
"""

DEFAULT_HEX_CONF = "C200001B2844"

_SPEED_BYTE = 3
_CHANNEL_BYTE = 4
_OPTION_BYTE = 5


def _dec_to_bin(dec: int, align_mod: int = 4) -> str:
    r = bin(dec)[2:]
    while align_mod > 0 and len(r) % align_mod != 0:
        r = "0" + r
    return r


def _set_bit(buf: bytearray, byte: int, bit: int, value: bool) -> None:
    c = "1" if value else "0"
    o = _dec_to_bin(buf[byte])
    lsb = 7 - bit
    o = o[:lsb] + c + o[lsb + 1 :]
    buf[byte] = int(o, 2)


def _set_dec_bits(buf: bytearray, byte: int, frm: int, length: int, value: int) -> None:
    b_value = _dec_to_bin(value, length)
    for i in range(length):
        _set_bit(buf, byte, frm + i, b_value[length - 1 - i] == "1")


def build_hex_conf(*, channel: int, speed: int, fec: bool) -> str:
    buf = bytearray.fromhex(DEFAULT_HEX_CONF)
    if len(buf) != 6:
        raise ValueError("invalid base hex conf")

    _set_dec_bits(buf, _SPEED_BYTE, 0, 3, speed)
    _set_dec_bits(buf, _CHANNEL_BYTE, 0, 6, channel)
    _set_bit(buf, _OPTION_BYTE, 2, fec)

    return buf.hex().upper()


def _self_test() -> None:
    # Legacy's own DefaultLoraState: channel=40, speed=3 (index into
    # airDataRates == 4.8 kbps), fec=True -- must reproduce the base
    # DEFAULT_HEX_CONF string unchanged, exactly like legacy's testHexConf().
    result = build_hex_conf(channel=40, speed=3, fec=True)
    if result != DEFAULT_HEX_CONF:
        raise AssertionError(f"hex conf is buggy: got {result} instead of {DEFAULT_HEX_CONF}")


_self_test()
