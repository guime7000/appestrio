import uuid
from datetime import datetime

from sqlmodel import Session, func, select

from app.models import (
    MAX_DEVICES_PER_TYPE,
    Calendar,
    CalendarCreate,
    CalendarUpdate,
    Device,
    DeviceCreate,
    DevicePublic,
    DeviceType,
    DeviceUpdate,
    Group,
    GroupCreate,
    GroupUpdate,
    IgnitionPreset,
    IgnitionPresetCreate,
    IgnitionPresetUpdate,
    LoraSettings,
    LoraSettingsUpdate,
    utcnow,
)
from app.models.calendars import CalendarPublic
from app.models.ignition_presets import DATE_FORMAT, TIME_FORMAT


class DeviceNotFoundError(Exception):
    def __init__(self, missing_device_ids: list[str]) -> None:
        self.missing_device_ids = missing_device_ids


class IgnitionPresetOverlapError(Exception):
    pass


class IgnitionPresetDateRangeError(Exception):
    pass


# --- LoRa config-sync bookkeeping -------------------------------------
#
# bump_* helpers only add to the session; they never commit -- each one is
# called from inside another crud function's existing single-commit
# transaction, so a mutation and the config_version bumps it triggers always
# land atomically together.


def bump_device_config_version(*, session: Session, device: Device) -> None:
    device.config_version += 1
    session.add(device)


def bump_config_version_for_devices(*, session: Session, devices: list[Device]) -> None:
    for device in devices:
        bump_device_config_version(session=session, device=device)


def bump_config_version_for_group(*, session: Session, group: Group) -> None:
    bump_config_version_for_devices(session=session, devices=group.devices)


def bump_config_version_for_calendar(*, session: Session, calendar: Calendar) -> None:
    for group in calendar.groups:
        bump_config_version_for_group(session=session, group=group)


def bump_config_version_for_calendar_id(*, session: Session, calendar_id: uuid.UUID) -> None:
    calendar = session.get(Calendar, calendar_id)
    if calendar:
        bump_config_version_for_calendar(session=session, calendar=calendar)


def get_devices_pending_sync(*, session: Session) -> list[Device]:
    # The "queue" the LoRa daemon will consume: any device whose
    # master-authoritative config_version hasn't been confirmed applied yet.
    # Deliberately not a literal append-only log of sync jobs -- several
    # edits landing before the daemon ever looks just move the target
    # number, so there's nothing to deduplicate and no backlog that grows
    # with edit count, only with genuinely-unsynced device count.
    return list(
        session.exec(
            select(Device)
            .where(Device.config_version != Device.synced_version)
            .order_by(Device.updated_at)
        ).all()
    )


def mark_device_synced(*, session: Session, device: Device, version: int) -> Device:
    # Contract for the (not yet built) daemon calling this -- both parts
    # matter, and getting either wrong silently defeats the sync check:
    #
    # 1. `version` must come from the device's own self-reported version in
    #    a PONG, never from "I finished sending the last chunk". Setting it
    #    right after transmit would only prove master *sent* something, not
    #    that the device received and applied it -- exactly the gap
    #    config_version exists to catch.
    # 2. Call this on *every* PONG received, not only right after a
    #    deliberate push. A device already marked synced can still drift
    #    later (factory reset, re-flash, corrupted storage); since the ping
    #    heartbeat already cycles through every known device continuously,
    #    always reconciling synced_version from live PONG data makes the
    #    check self-healing against drift from any cause -- the same way
    #    every PONG's activeState byte must reconcile into Device.active
    #    (see Lora_Rewrite_Plan.md §9.7/§9's PONG-reconciliation notes).
    device.synced_version = version
    session.add(device)
    session.commit()
    session.refresh(device)
    return device


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
    weekdays_changed = (
        "weekdays" in update_data and update_data["weekdays"] != db_calendar.weekdays
    )
    db_calendar.sqlmodel_update(update_data)
    db_calendar.updated_at = utcnow()
    session.add(db_calendar)
    if weekdays_changed:
        bump_config_version_for_calendar(session=session, calendar=db_calendar)
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
    bump_config_version_for_calendar_id(
        session=session, calendar_id=ignition_preset_create.calendar_id
    )
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
    old_calendar_id = db_ignition_preset.calendar_id
    db_ignition_preset.sqlmodel_update(update_data)
    db_ignition_preset.updated_at = utcnow()
    session.add(db_ignition_preset)
    # Always bump the preset's original calendar -- covers both a plain
    # field edit (old == new calendar) and a move away from it. Bump the
    # destination calendar too when it's actually a move.
    bump_config_version_for_calendar_id(session=session, calendar_id=old_calendar_id)
    if db_ignition_preset.calendar_id != old_calendar_id:
        bump_config_version_for_calendar_id(
            session=session, calendar_id=db_ignition_preset.calendar_id
        )
    session.commit()
    session.refresh(db_ignition_preset)
    return db_ignition_preset


def delete_ignition_preset(*, session: Session, db_ignition_preset: IgnitionPreset) -> None:
    bump_config_version_for_calendar_id(
        session=session, calendar_id=db_ignition_preset.calendar_id
    )
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
    calendar_changed = (
        "calendar_id" in update_data and update_data["calendar_id"] != db_group.calendar_id
    )
    db_group.sqlmodel_update(update_data)
    db_group.updated_at = utcnow()
    session.add(db_group)
    if calendar_changed:
        bump_config_version_for_group(session=session, group=db_group)
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
    *, session: Session, db_group: Group, device_ids: list[str]
) -> Group:
    unique_ids = set(device_ids)
    devices = session.exec(
        select(Device).where(Device.device_id.in_(unique_ids))  # type: ignore[attr-defined]
    ).all()
    if len(devices) != len(unique_ids):
        missing = unique_ids - {device.device_id for device in devices}
        raise DeviceNotFoundError(sorted(missing))

    for device in list(db_group.devices):
        if device.device_id not in unique_ids:
            device.group_id = None
            bump_device_config_version(session=session, device=device)
            session.add(device)

    for device in devices:
        if device.group_id != db_group.uuid:
            device.group_id = db_group.uuid
            bump_device_config_version(session=session, device=device)
        session.add(device)

    session.commit()
    session.refresh(db_group)
    return db_group


def create_device(*, session: Session, device_create: DeviceCreate) -> Device:
    device_id = f"{device_create.device_type.value}{device_create.device_number}"
    device_data = device_create.model_dump(exclude={"device_number"})
    db_device = Device.model_validate(device_data, update={"device_id": device_id})
    session.add(db_device)
    session.commit()
    session.refresh(db_device)
    return db_device


def get_free_device_numbers(*, session: Session) -> dict[DeviceType, list[int]]:
    free_numbers: dict[DeviceType, list[int]] = {}
    for device_type in DeviceType:
        prefix = device_type.value
        used = set()
        devices = session.exec(
            select(Device).where(Device.device_type == device_type)
        ).all()
        for device in devices:
            suffix = device.device_id.removeprefix(prefix)
            if suffix.isdigit():
                used.add(int(suffix))
        free_numbers[device_type] = [
            number for number in range(MAX_DEVICES_PER_TYPE) if number not in used
        ]
    return free_numbers


def get_device(*, session: Session, device_uuid: uuid.UUID) -> Device | None:
    return session.get(Device, device_uuid)


def get_device_by_device_id(*, session: Session, device_id: str) -> Device | None:
    return session.exec(select(Device).where(Device.device_id == device_id)).first()


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
    if update_data:
        bump_device_config_version(session=session, device=db_device)
    session.add(db_device)
    session.commit()
    session.refresh(db_device)
    return db_device


def delete_device(*, session: Session, db_device: Device) -> None:
    session.delete(db_device)
    session.commit()


def get_devices_by_device_ids(*, session: Session, device_ids: list[str]) -> list[Device]:
    unique_ids = set(device_ids)
    return list(
        session.exec(
            select(Device).where(Device.device_id.in_(unique_ids))  # type: ignore[attr-defined]
        ).all()
    )


def delete_devices(*, session: Session, db_devices: list[Device]) -> None:
    for db_device in db_devices:
        session.delete(db_device)
    session.commit()


def device_to_public(device: Device) -> DevicePublic:
    calendar = device.group.calendar if device.group else None
    return DevicePublic(
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


def get_lora_settings(*, session: Session) -> LoraSettings:
    settings = session.get(LoraSettings, 1)
    if settings is None:
        # Get-or-create safety net: production DBs get this row from the
        # migration's data seed, but a schema built straight from the
        # models (e.g. in tests) won't have it yet -- callers should never
        # have to special-case "the singleton doesn't exist".
        settings = LoraSettings()
        session.add(settings)
        session.commit()
        session.refresh(settings)
    return settings


def update_lora_settings(
    *, session: Session, settings_in: LoraSettingsUpdate
) -> LoraSettings:
    settings = get_lora_settings(session=session)
    update_data = settings_in.model_dump(exclude_unset=True)
    settings.sqlmodel_update(update_data)
    settings.updated_at = utcnow()
    session.add(settings)
    session.commit()
    session.refresh(settings)
    return settings
