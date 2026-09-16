from sqlmodel import SQLModel

from app.models.calendars import (
    Calendar,
    CalendarBase,
    CalendarCreate,
    CalendarPublic,
    CalendarsPublic,
    CalendarSummaryPublic,
    CalendarUpdate,
)
from app.models.common import BulkDeleteRequest, Message, utcnow
from app.models.devices import (
    LORA_TYPE_INDEX,
    MAX_DEVICES_PER_TYPE,
    Device,
    DeviceBase,
    DeviceBulkDeleteRequest,
    DeviceCreate,
    DevicePublic,
    DevicesPublic,
    DeviceType,
    DeviceUpdate,
    FreeDeviceNumbers,
)
from app.models.groups import (
    Group,
    GroupBase,
    GroupCreate,
    GroupDevicePublic,
    GroupDevicesUpdate,
    GroupPublic,
    GroupsPublic,
    GroupUpdate,
)
from app.models.ignition_presets import (
    IgnitionPreset,
    IgnitionPresetBase,
    IgnitionPresetCreate,
    IgnitionPresetPublic,
    IgnitionPresetsPublic,
    IgnitionPresetUpdate,
)
from app.models.lora_settings import (
    DEFAULT_CHANNEL,
    DEFAULT_CLOCK_INTERVAL_S,
    DEFAULT_PING_INTERVAL_S,
    DEFAULT_SPEED,
    MAX_LORA_CHANNEL,
    MIN_CLOCK_INTERVAL_S,
    MIN_PING_INTERVAL_S,
    NUM_AIR_DATA_RATES,
    LoraSettings,
    LoraSettingsBase,
    LoraSettingsPublic,
    LoraSettingsUpdate,
)

# Calendar.groups / Device.group reference Group through a string forward ref
# (TYPE_CHECKING-only import in calendars.py/devices.py) to avoid a circular
# import, since Group itself imports Calendar and Device. Same story for
# IgnitionPreset.calendar, which only sees Calendar via TYPE_CHECKING to avoid
# a cycle the other way (calendars.py imports IgnitionPreset directly for its
# ignition_presets relationship and CalendarPublic's nested list). Now that
# every model is fully defined, resolve those forward refs.
Calendar.model_rebuild(_types_namespace={"Group": Group})
Device.model_rebuild(_types_namespace={"Group": Group})
IgnitionPreset.model_rebuild(_types_namespace={"Calendar": Calendar})

__all__ = [
    "SQLModel",
    "LORA_TYPE_INDEX",
    "MAX_DEVICES_PER_TYPE",
    "BulkDeleteRequest",
    "Calendar",
    "CalendarBase",
    "CalendarCreate",
    "CalendarPublic",
    "CalendarsPublic",
    "CalendarSummaryPublic",
    "CalendarUpdate",
    "Device",
    "DeviceBase",
    "DeviceBulkDeleteRequest",
    "DeviceCreate",
    "DevicePublic",
    "DevicesPublic",
    "DeviceType",
    "DeviceUpdate",
    "FreeDeviceNumbers",
    "Group",
    "GroupBase",
    "GroupCreate",
    "GroupDevicePublic",
    "GroupDevicesUpdate",
    "GroupPublic",
    "GroupsPublic",
    "GroupUpdate",
    "IgnitionPreset",
    "IgnitionPresetBase",
    "IgnitionPresetCreate",
    "IgnitionPresetPublic",
    "IgnitionPresetsPublic",
    "IgnitionPresetUpdate",
    "DEFAULT_CHANNEL",
    "DEFAULT_CLOCK_INTERVAL_S",
    "DEFAULT_PING_INTERVAL_S",
    "DEFAULT_SPEED",
    "MAX_LORA_CHANNEL",
    "MIN_CLOCK_INTERVAL_S",
    "MIN_PING_INTERVAL_S",
    "NUM_AIR_DATA_RATES",
    "LoraSettings",
    "LoraSettingsBase",
    "LoraSettingsPublic",
    "LoraSettingsUpdate",
    "Message",
    "utcnow",
]
