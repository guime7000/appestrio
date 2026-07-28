import uuid
from copy import deepcopy

from sqlmodel import Session, func, select

from app.models import (
    Calendar,
    CalendarCreate,
    CalendarPublic,
    CalendarUpdate,
    Device,
    DeviceCreate,
    DevicePublic,
    DeviceUpdate,
    Group,
    GroupCreate,
    GroupUpdate,
    utcnow,
)


class DeviceNotFoundError(Exception):
    def __init__(self, missing_uuids: list[uuid.UUID]) -> None:
        self.missing_uuids = missing_uuids


def create_calendar(*, session: Session, calendar_create: CalendarCreate) -> Calendar:
    db_calendar = Calendar(
        label=calendar_create.label,
        presets=calendar_create.presets or {},
        days=calendar_create.days or {},
    )
    session.add(db_calendar)
    session.commit()
    session.refresh(db_calendar)
    return db_calendar


def get_calendar(*, session: Session, calendar_uuid: uuid.UUID) -> Calendar | None:
    return session.get(Calendar, calendar_uuid)


def duplicate_calendar(*, session: Session, db_calendar: Calendar) -> Calendar:
    duplicate = Calendar(
        label=f"{db_calendar.label} copy",
        presets=deepcopy(db_calendar.presets),
        days=deepcopy(db_calendar.days),
    )
    session.add(duplicate)
    session.commit()
    session.refresh(duplicate)
    return duplicate


def get_calendars(
    *, session: Session, skip: int = 0, limit: int = 100
) -> tuple[list[Calendar], int]:
    count = session.exec(select(func.count()).select_from(Calendar)).one()
    calendars = session.exec(select(Calendar).offset(skip).limit(limit)).all()
    return list(calendars), count


def update_calendar(
    *, session: Session, db_calendar: Calendar, calendar_in: CalendarUpdate
) -> Calendar:
    update_data = calendar_in.model_dump(exclude_unset=True)
    # presets/days are non-nullable on the table; treat an explicit null as
    # "clear it" the same way create_calendar treats a null on creation.
    for nullable_json_field in ("presets", "days"):
        if nullable_json_field in update_data and update_data[nullable_json_field] is None:
            update_data[nullable_json_field] = {}
    db_calendar.sqlmodel_update(update_data)
    db_calendar.updated_at = utcnow()
    session.add(db_calendar)
    session.commit()
    session.refresh(db_calendar)
    return db_calendar


def delete_calendar(*, session: Session, db_calendar: Calendar) -> None:
    session.delete(db_calendar)
    session.commit()


def create_group(*, session: Session, group_create: GroupCreate) -> Group:
    db_group = Group.model_validate(group_create)
    session.add(db_group)
    session.commit()
    session.refresh(db_group)
    return db_group


def get_group(*, session: Session, group_uuid: uuid.UUID) -> Group | None:
    return session.get(Group, group_uuid)


def get_groups(
    *, session: Session, skip: int = 0, limit: int = 100
) -> tuple[list[Group], int]:
    count = session.exec(select(func.count()).select_from(Group)).one()
    groups = session.exec(select(Group).offset(skip).limit(limit)).all()
    return list(groups), count


def update_group(
    *, session: Session, db_group: Group, group_in: GroupUpdate
) -> Group:
    update_data = group_in.model_dump(exclude_unset=True)
    db_group.sqlmodel_update(update_data)
    db_group.updated_at = utcnow()
    session.add(db_group)
    session.commit()
    session.refresh(db_group)
    return db_group


def delete_group(*, session: Session, db_group: Group) -> None:
    session.delete(db_group)
    session.commit()


def set_group_devices(
    *, session: Session, db_group: Group, device_uuids: list[uuid.UUID]
) -> Group:
    unique_uuids = set(device_uuids)
    devices = session.exec(
        select(Device).where(Device.uuid.in_(unique_uuids))  # type: ignore[attr-defined]
    ).all()
    if len(devices) != len(unique_uuids):
        missing = unique_uuids - {device.uuid for device in devices}
        raise DeviceNotFoundError(sorted(missing))

    for device in list(db_group.devices):
        if device.uuid not in unique_uuids:
            device.group_id = None
            session.add(device)

    for device in devices:
        device.group_id = db_group.uuid
        session.add(device)

    session.commit()
    session.refresh(db_group)
    return db_group


def create_device(*, session: Session, device_create: DeviceCreate) -> Device:
    db_device = Device.model_validate(device_create)
    session.add(db_device)
    session.commit()
    session.refresh(db_device)
    return db_device


def get_device(*, session: Session, device_uuid: uuid.UUID) -> Device | None:
    return session.get(Device, device_uuid)


def get_devices(
    *, session: Session, skip: int = 0, limit: int = 100
) -> tuple[list[Device], int]:
    count = session.exec(select(func.count()).select_from(Device)).one()
    devices = session.exec(select(Device).offset(skip).limit(limit)).all()
    return list(devices), count


def update_device(
    *, session: Session, db_device: Device, device_in: DeviceUpdate
) -> Device:
    update_data = device_in.model_dump(exclude_unset=True)
    db_device.sqlmodel_update(update_data)
    db_device.updated_at = utcnow()
    session.add(db_device)
    session.commit()
    session.refresh(db_device)
    return db_device


def delete_device(*, session: Session, db_device: Device) -> None:
    session.delete(db_device)
    session.commit()


def device_to_public(device: Device) -> DevicePublic:
    calendar = device.group.calendar if device.group else None
    return DevicePublic(
        uuid=device.uuid,
        device_id=device.device_id,
        device_name=device.device_name,
        active=device.active,
        group=device.group.label if device.group else None,
        calendar=CalendarPublic.model_validate(calendar) if calendar else None,
        audiofile=device.audiofile,
        ip=device.ip,
        master_ip=device.master_ip,
        updated_at=device.updated_at,
    )
