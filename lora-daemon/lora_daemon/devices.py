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


def device_id_for_identity(device_type: LoraDeviceType, device_number: int) -> str:
    """Inverse of parse_device_identity_from_hostname -- reconstructs the
    device_id string (e.g. "lumestrio3") backend's own DeviceCreate
    contract expects, from a parsed (type, number) pair.
    """
    return f"{device_type.name.lower()}{device_number}"


def parse_device_identity_from_hostname(hostname: str) -> tuple[LoraDeviceType, int]:
    """Self-identification for a lumestrio endpoint: derives this
    device's own (device_type, device_number) from its OS hostname --
    there's no local setup step at all (every other config field comes
    from master via LoRa, see Lora_Rewrite_Plan.md item 8's provisioning-
    model note), so a fresh device needs to know its own identity from
    something outside the app entirely before it's ever heard from
    master -- it needs its own address just to recognize which LoRa
    messages target it. Mirrors legacy's own sys.getHostName() pattern:
    the hostname itself IS the device_id (e.g. "lumestrio3"), set once at
    image/flash time (OS/hardware provisioning, not an app-level step --
    and also what avahi/mDNS already advertises).

    A hostname that includes a domain suffix (e.g. "lumestrio3.local")
    is handled by only looking at the part before the first ".",
    defensively -- `socket.gethostname()` normally returns the short
    name alone on Linux, but this shouldn't silently misparse if it ever
    doesn't.

    In practice this only ever runs for `lumestrio` -- `relaystrio` is
    frozen ESP32 firmware, not this Python process -- but both prefixes
    are recognized here for symmetry with every other address-parsing
    helper in this module, and so a misconfigured hostname on a
    `relaystrio`-named Pi (which should never exist) fails loudly rather
    than silently.
    """
    short_hostname = hostname.split(".", 1)[0]
    for device_type in LoraDeviceType:
        prefix = device_type.name.lower()
        if short_hostname.startswith(prefix):
            suffix = short_hostname[len(prefix) :]
            if suffix.isdigit():
                return device_type, int(suffix)
    raise ValueError(
        f"hostname {hostname!r} doesn't match the <device_type><number> convention "
        f"(expected one of: {', '.join(t.name.lower() for t in LoraDeviceType)})"
    )
