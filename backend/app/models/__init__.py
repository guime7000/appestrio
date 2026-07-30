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
    Device,
    DeviceBase,
    DeviceCreate,
    DevicePublic,
    DevicesPublic,
    DeviceUpdate,
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

# Calendar.groups / Device.group reference Group through a string forward ref
# (TYPE_CHECKING-only import in calendars.py/devices.py) to avoid a circular
# import, since Group itself imports Calendar and Device. Now that Group is
# fully defined, resolve those forward refs.
Calendar.model_rebuild(_types_namespace={"Group": Group})
Device.model_rebuild(_types_namespace={"Group": Group})

__all__ = [
    "SQLModel",
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
    "DeviceCreate",
    "DevicePublic",
    "DevicesPublic",
    "DeviceUpdate",
    "Group",
    "GroupBase",
    "GroupCreate",
    "GroupDevicePublic",
    "GroupDevicesUpdate",
    "GroupPublic",
    "GroupsPublic",
    "GroupUpdate",
    "Message",
    "utcnow",
]
