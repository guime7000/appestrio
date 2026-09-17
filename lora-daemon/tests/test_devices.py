import pytest

from lora_daemon.devices import LoraDeviceType, build_address, describe_address


def test_relaystrio_is_zero_lumestrio_is_one() -> None:
    # Pinned: matches both legacy's LoraDeviceType enum and appestrio
    # backend's LORA_TYPE_INDEX mapping. If this ever drifts, addresses
    # computed here stop matching what burger/relaystrio firmware expect.
    assert int(LoraDeviceType.RELAYSTRIO) == 0
    assert int(LoraDeviceType.LUMESTRIO) == 1


def test_build_address_relaystrio_uses_low_range() -> None:
    assert build_address(0, LoraDeviceType.RELAYSTRIO) == 0
    assert build_address(31, LoraDeviceType.RELAYSTRIO) == 31


def test_build_address_lumestrio_uses_high_range() -> None:
    assert build_address(0, LoraDeviceType.LUMESTRIO) == 32
    assert build_address(31, LoraDeviceType.LUMESTRIO) == 63


def test_build_address_rejects_out_of_range_number() -> None:
    with pytest.raises(ValueError, match="out of range"):
        build_address(32, LoraDeviceType.RELAYSTRIO)
    with pytest.raises(ValueError, match="out of range"):
        build_address(-1, LoraDeviceType.RELAYSTRIO)


@pytest.mark.parametrize(
    ("device_type", "device_number"),
    [
        (LoraDeviceType.RELAYSTRIO, 0),
        (LoraDeviceType.RELAYSTRIO, 31),
        (LoraDeviceType.LUMESTRIO, 0),
        (LoraDeviceType.LUMESTRIO, 31),
    ],
)
def test_describe_address_inverts_build_address(
    device_type: LoraDeviceType, device_number: int
) -> None:
    address = build_address(device_number, device_type)
    assert describe_address(address) == (device_type, device_number)
