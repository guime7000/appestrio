import uuid

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
    utcnow,
)


def create_calendar(*, session: Session, calendar_create: CalendarCreate) -> Calendar:
    db_calendar = Calendar.model_validate(calendar_create)
    session.add(db_calendar)
    session.commit()
    session.refresh(db_calendar)
    return db_calendar


def get_calendar(*, session: Session, calendar_uuid: uuid.UUID) -> Calendar | None:
    return session.get(Calendar, calendar_uuid)


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
    db_calendar.sqlmodel_update(update_data)
    db_calendar.updated_at = utcnow()
    session.add(db_calendar)
    session.commit()
    session.refresh(db_calendar)
    return db_calendar


def delete_calendar(*, session: Session, db_calendar: Calendar) -> None:
    session.delete(db_calendar)
    session.commit()


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
