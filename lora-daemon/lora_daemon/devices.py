"""LoRa device addressing.

Ported from legacy's LoraDevice.ts. The address space is one byte:
`address = device_number + MAX_DEVICES_PER_TYPE * device_type`, with 255
reserved as the broadcast address (BROADCAST_ADDRESS in constants.py) --
never a real device's address, so MAX_DEVICES_PER_TYPE * 2 (64) must stay
well under 255.

RELAYSTRIO=0 / LUMESTRIO=1 matches both legacy's `LoraDeviceType` enum and
appestrio backend's `LORA_TYPE_INDEX` mapping (app/models/devices.py) --
this is the one place, across the whole system, this convention has to
hold, so it's pinned by a test here too.
"""

from enum import IntEnum

MAX_DEVICES_PER_TYPE = 32


class LoraDeviceType(IntEnum):
    RELAYSTRIO = 0
    LUMESTRIO = 1


def build_address(device_number: int, device_type: LoraDeviceType) -> int:
    if not 0 <= device_number < MAX_DEVICES_PER_TYPE:
        raise ValueError(f"device_number {device_number} out of range")
    return device_number + MAX_DEVICES_PER_TYPE * int(device_type)


def describe_address(address: int) -> tuple[LoraDeviceType, int]:
    """Inverse of build_address -- (device_type, device_number)."""
    return LoraDeviceType(address // MAX_DEVICES_PER_TYPE), address % MAX_DEVICES_PER_TYPE


def address_for_device_id(device_id: str, device_type: str) -> int:
    """Parses a device's LoRa address straight from its (device_type,
    device_number)-encoded device_id (e.g. "lumestrio3" -> address 3 +
    32*LUMESTRIO), matching backend's DeviceCreate contract (device_id is
    always derived server-side this way -- app/models/devices.py) and
    legacy's own equivalent (parsing the Pi's hostname the same way in
    LoraModule's constructor).
    """
    if not device_id.startswith(device_type):
        raise ValueError(f"device_id {device_id!r} doesn't match device_type {device_type!r}")
    number_part = device_id[len(device_type) :]
    if not number_part.isdigit():
        raise ValueError(f"device_id {device_id!r} has no numeric suffix after {device_type!r}")
    lora_type = LoraDeviceType[device_type.upper()]
    return build_address(int(number_part), lora_type)
