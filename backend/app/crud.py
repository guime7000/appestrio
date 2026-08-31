import uuid
from datetime import datetime

from sqlmodel import Session, func, select

from app.models import (
    Calendar,
    CalendarCreate,
    CalendarUpdate,
    Device,
    DeviceCreate,
    DevicePublic,
    DeviceUpdate,
    Group,
    GroupCreate,
    GroupUpdate,
    IgnitionPreset,
    IgnitionPresetCreate,
    IgnitionPresetUpdate,
    utcnow,
)
from app.models.calendars import CalendarPublic
from app.models.ignition_presets import DATE_FORMAT, TIME_FORMAT


class DeviceNotFoundError(Exception):
    def __init__(self, missing_uuids: list[uuid.UUID]) -> None:
        self.missing_uuids = missing_uuids


class IgnitionPresetOverlapError(Exception):
    pass


class IgnitionPresetDateRangeError(Exception):
    pass


def create_calendar(*, session: Session, calendar_create: CalendarCreate) -> Calendar:
    db_calendar = Calendar(label=calendar_create.label, weekdays=calendar_create.weekdays)
    session.add(db_calendar)
    session.commit()
    session.refresh(db_calendar)
    return db_calendar


def get_calendar(*, session: Session, calendar_uuid: uuid.UUID) -> Calendar | None:
    return session.get(Calendar, calendar_uuid)


def duplicate_calendar(*, session: Session, db_calendar: Calendar) -> Calendar:
    duplicate = Calendar(
        label=f"{db_calendar.label} copy",
        weekdays=list(db_calendar.weekdays),
    )
    session.add(duplicate)
    for preset in db_calendar.ignition_presets:
        session.add(
            IgnitionPreset(
                name=preset.name,
                description=preset.description,
                start_date=preset.start_date,
                stop_date=preset.stop_date,
                start_time=preset.start_time,
                stop_time=preset.stop_time,
                calendar_id=duplicate.uuid,
            )
        )
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
    # weekdays is non-nullable on the table; treat an explicit null as
    # "clear it" the same way create_calendar treats an omitted list.
    if "weekdays" in update_data and update_data["weekdays"] is None:
        update_data["weekdays"] = []
    db_calendar.sqlmodel_update(update_data)
    db_calendar.updated_at = utcnow()
    session.add(db_calendar)
    session.commit()
    session.refresh(db_calendar)
    return db_calendar


def delete_calendar(*, session: Session, db_calendar: Calendar) -> None:
    session.delete(db_calendar)
    session.commit()


def get_calendars_by_uuids(
    *, session: Session, uuids: list[uuid.UUID]
) -> list[Calendar]:
    unique_uuids = set(uuids)
    return list(
        session.exec(
            select(Calendar).where(Calendar.uuid.in_(unique_uuids))  # type: ignore[attr-defined]
        ).all()
    )


def delete_calendars(*, session: Session, db_calendars: list[Calendar]) -> None:
    for db_calendar in db_calendars:
        session.delete(db_calendar)
    session.commit()


def _date_ranges_overlap(start_a: str, stop_a: str, start_b: str, stop_b: str) -> bool:
    a_start = datetime.strptime(start_a, DATE_FORMAT)
    a_stop = datetime.strptime(stop_a, DATE_FORMAT)
    b_start = datetime.strptime(start_b, DATE_FORMAT)
    b_stop = datetime.strptime(stop_b, DATE_FORMAT)
    return a_start <= b_stop and b_start <= a_stop


def _time_ranges_overlap(start_a: str, stop_a: str, start_b: str, stop_b: str) -> bool:
    # Strict "<" so back-to-back windows (one stopping exactly when the other
    # starts) are allowed, not just windows that share no instant at all.
    # Assumes same-day windows (start_time <= stop_time); a window crossing
    # midnight isn't modeled here.
    a_start = datetime.strptime(start_a, TIME_FORMAT)
    a_stop = datetime.strptime(stop_a, TIME_FORMAT)
    b_start = datetime.strptime(start_b, TIME_FORMAT)
    b_stop = datetime.strptime(stop_b, TIME_FORMAT)
    return a_start < b_stop and b_start < a_stop


def _check_no_overlap(
    *,
    session: Session,
    calendar_id: uuid.UUID,
    start_date: str,
    stop_date: str,
    start_time: str,
    stop_time: str,
    exclude_uuid: uuid.UUID | None = None,
) -> None:
    existing = session.exec(
        select(IgnitionPreset).where(IgnitionPreset.calendar_id == calendar_id)
    ).all()
    for preset in existing:
        if exclude_uuid is not None and preset.uuid == exclude_uuid:
            continue
        # Two presets only actually conflict if their active days AND their
        # daily time windows overlap -- same dates but different times of day
        # (e.g. an afternoon slot and an evening slot) are perfectly fine.
        if _date_ranges_overlap(
            start_date, stop_date, preset.start_date, preset.stop_date
        ) and _time_ranges_overlap(start_time, stop_time, preset.start_time, preset.stop_time):
            raise IgnitionPresetOverlapError(
                f"Date/time range overlaps with existing ignition_preset "
                f"{preset.uuid} ({preset.name})"
            )


def create_ignition_preset(
    *, session: Session, ignition_preset_create: IgnitionPresetCreate
) -> IgnitionPreset:
    _check_no_overlap(
        session=session,
        calendar_id=ignition_preset_create.calendar_id,
        start_date=ignition_preset_create.start_date,
        stop_date=ignition_preset_create.stop_date,
        start_time=ignition_preset_create.start_time,
        stop_time=ignition_preset_create.stop_time,
    )
    db_ignition_preset = IgnitionPreset.model_validate(ignition_preset_create)
    session.add(db_ignition_preset)
    session.commit()
    session.refresh(db_ignition_preset)
    return db_ignition_preset


def get_ignition_preset(
    *, session: Session, ignition_preset_uuid: uuid.UUID
) -> IgnitionPreset | None:
    return session.get(IgnitionPreset, ignition_preset_uuid)


def get_ignition_presets(
    *, session: Session, skip: int = 0, limit: int = 100
) -> tuple[list[IgnitionPreset], int]:
    count = session.exec(select(func.count()).select_from(IgnitionPreset)).one()
    presets = session.exec(select(IgnitionPreset).offset(skip).limit(limit)).all()
    return list(presets), count


def update_ignition_preset(
    *,
    session: Session,
    db_ignition_preset: IgnitionPreset,
    ignition_preset_in: IgnitionPresetUpdate,
) -> IgnitionPreset:
    update_data = ignition_preset_in.model_dump(exclude_unset=True)
    calendar_id = update_data.get("calendar_id", db_ignition_preset.calendar_id)
    start_date = update_data.get("start_date", db_ignition_preset.start_date)
    stop_date = update_data.get("stop_date", db_ignition_preset.stop_date)
    start_time = update_data.get("start_time", db_ignition_preset.start_time)
    stop_time = update_data.get("stop_time", db_ignition_preset.stop_time)
    if datetime.strptime(start_date, DATE_FORMAT) > datetime.strptime(stop_date, DATE_FORMAT):
        raise IgnitionPresetDateRangeError("start_date must not be after stop_date")
    _check_no_overlap(
        session=session,
        calendar_id=calendar_id,
        start_date=start_date,
        stop_date=stop_date,
        start_time=start_time,
        stop_time=stop_time,
        exclude_uuid=db_ignition_preset.uuid,
    )
    db_ignition_preset.sqlmodel_update(update_data)
    db_ignition_preset.updated_at = utcnow()
    session.add(db_ignition_preset)
    session.commit()
    session.refresh(db_ignition_preset)
    return db_ignition_preset


def delete_ignition_preset(*, session: Session, db_ignition_preset: IgnitionPreset) -> None:
    session.delete(db_ignition_preset)
    session.commit()


def get_ignition_presets_by_uuids(
    *, session: Session, uuids: list[uuid.UUID]
) -> list[IgnitionPreset]:
    unique_uuids = set(uuids)
    return list(
        session.exec(
            select(IgnitionPreset).where(IgnitionPreset.uuid.in_(unique_uuids))  # type: ignore[attr-defined]
        ).all()
    )


def delete_ignition_presets(
    *, session: Session, db_ignition_presets: list[IgnitionPreset]
) -> None:
    for db_ignition_preset in db_ignition_presets:
        session.delete(db_ignition_preset)
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


def get_groups_by_uuids(*, session: Session, uuids: list[uuid.UUID]) -> list[Group]:
    unique_uuids = set(uuids)
    return list(
        session.exec(
            select(Group).where(Group.uuid.in_(unique_uuids))  # type: ignore[attr-defined]
        ).all()
    )


def delete_groups(*, session: Session, db_groups: list[Group]) -> None:
    for db_group in db_groups:
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


def get_devices_by_uuids(*, session: Session, uuids: list[uuid.UUID]) -> list[Device]:
    unique_uuids = set(uuids)
    return list(
        session.exec(
            select(Device).where(Device.uuid.in_(unique_uuids))  # type: ignore[attr-defined]
        ).all()
    )


def delete_devices(*, session: Session, db_devices: list[Device]) -> None:
    for db_device in db_devices:
        session.delete(db_device)
    session.commit()


def device_to_public(device: Device) -> DevicePublic:
    calendar = device.group.calendar if device.group else None
    return DevicePublic(
        uuid=device.uuid,
        device_id=device.device_id,
        device_name=device.device_name,
        device_type=device.device_type,
        active=device.active,
        is_master=device.is_master,
        handles_audio=device.handles_audio,
        handles_dmx=device.handles_dmx,
        group=device.group.label if device.group else None,
        group_id=device.group.uuid if device.group else None,
        calendar=CalendarPublic.model_validate(calendar) if calendar else None,
        audiofile=device.audiofile,
        ip=device.ip,
        master_ip=device.master_ip,
        updated_at=device.updated_at,
    )
