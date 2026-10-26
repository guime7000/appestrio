import pytest

from lora_daemon.devices import (
    LoraDeviceType,
    address_for_device_id,
    build_address,
    describe_address,
    device_id_for_identity,
    parse_device_identity_from_hostname,
)


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


def test_address_for_device_id_lumestrio() -> None:
    assert address_for_device_id("lumestrio3", "lumestrio") == build_address(
        3, LoraDeviceType.LUMESTRIO
    )


def test_address_for_device_id_relaystrio() -> None:
    assert address_for_device_id("relaystrio7", "relaystrio") == build_address(
        7, LoraDeviceType.RELAYSTRIO
    )


def test_address_for_device_id_rejects_prefix_mismatch() -> None:
    with pytest.raises(ValueError, match="doesn't match device_type"):
        address_for_device_id("relaystrio7", "lumestrio")


def test_address_for_device_id_rejects_non_numeric_suffix() -> None:
    with pytest.raises(ValueError, match="no numeric suffix"):
        address_for_device_id("lumestrio-master", "lumestrio")


def test_device_id_for_identity_lumestrio() -> None:
    assert device_id_for_identity(LoraDeviceType.LUMESTRIO, 3) == "lumestrio3"


def test_device_id_for_identity_relaystrio() -> None:
    assert device_id_for_identity(LoraDeviceType.RELAYSTRIO, 7) == "relaystrio7"


def test_parse_device_identity_from_hostname_lumestrio() -> None:
    assert parse_device_identity_from_hostname("lumestrio3") == (LoraDeviceType.LUMESTRIO, 3)


def test_parse_device_identity_from_hostname_relaystrio() -> None:
    assert parse_device_identity_from_hostname("relaystrio7") == (LoraDeviceType.RELAYSTRIO, 7)


def test_parse_device_identity_from_hostname_strips_domain_suffix() -> None:
    assert parse_device_identity_from_hostname("lumestrio3.local") == (
        LoraDeviceType.LUMESTRIO,
        3,
    )


def test_parse_device_identity_from_hostname_rejects_unknown_prefix() -> None:
    with pytest.raises(ValueError, match="doesn't match the"):
        parse_device_identity_from_hostname("raspberrypi")


def test_parse_device_identity_from_hostname_rejects_non_numeric_suffix() -> None:
    with pytest.raises(ValueError, match="doesn't match the"):
        parse_device_identity_from_hostname("lumestrio-master")


def test_parse_device_identity_from_hostname_round_trips_with_device_id_for_identity() -> None:
    device_type, device_number = parse_device_identity_from_hostname("lumestrio12")
    assert device_id_for_identity(device_type, device_number) == "lumestrio12"
