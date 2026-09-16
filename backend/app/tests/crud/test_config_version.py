from sqlmodel import Session

from app import crud
from app.models import (
    CalendarUpdate,
    DeviceCreate,
    DeviceUpdate,
    GroupCreate,
    GroupUpdate,
    IgnitionPresetCreate,
    IgnitionPresetUpdate,
)
from app.tests.utils import (
    create_calendar,
    create_group,
    create_ignition_preset,
    device_payload,
    group_payload,
    ignition_preset_payload,
)


def test_new_device_starts_pending_sync(session: Session) -> None:
    device = crud.create_device(session=session, device_create=DeviceCreate(**device_payload()))

    assert device.config_version == 1
    assert device.synced_version == 0
    assert device in crud.get_devices_pending_sync(session=session)


def test_update_device_bumps_config_version(session: Session) -> None:
    device = crud.create_device(session=session, device_create=DeviceCreate(**device_payload()))
    original_version = device.config_version

    updated = crud.update_device(
        session=session, db_device=device, device_in=DeviceUpdate(device_name="renamed")
    )

    assert updated.config_version == original_version + 1


def test_empty_update_device_does_not_bump_config_version(session: Session) -> None:
    device = crud.create_device(session=session, device_create=DeviceCreate(**device_payload()))
    original_version = device.config_version

    updated = crud.update_device(session=session, db_device=device, device_in=DeviceUpdate())

    assert updated.config_version == original_version


def test_set_group_devices_bumps_added_and_removed_devices(session: Session) -> None:
    group = crud.create_group(session=session, group_create=GroupCreate(**group_payload()))
    added = crud.create_device(session=session, device_create=DeviceCreate(**device_payload()))
    already_in_group = crud.create_device(
        session=session, device_create=DeviceCreate(**device_payload(group_id=group.uuid))
    )
    added_version = added.config_version
    already_in_group_version = already_in_group.config_version

    crud.set_group_devices(
        session=session, db_group=group, device_ids=[added.device_id, already_in_group.device_id]
    )
    session.refresh(added)
    session.refresh(already_in_group)

    assert added.config_version == added_version + 1
    # Resubmitting a device that was already in the group is a no-op for it.
    assert already_in_group.config_version == already_in_group_version


def test_set_group_devices_bumps_removed_device(session: Session) -> None:
    group = crud.create_group(session=session, group_create=GroupCreate(**group_payload()))
    device = crud.create_device(
        session=session, device_create=DeviceCreate(**device_payload(group_id=group.uuid))
    )
    original_version = device.config_version

    crud.set_group_devices(session=session, db_group=group, device_ids=[])
    session.refresh(device)

    assert device.group_id is None
    assert device.config_version == original_version + 1


def test_update_group_calendar_reassignment_bumps_its_devices(session: Session) -> None:
    calendar = create_calendar(session)
    group = crud.create_group(session=session, group_create=GroupCreate(**group_payload()))
    device = crud.create_device(
        session=session, device_create=DeviceCreate(**device_payload(group_id=group.uuid))
    )
    original_version = device.config_version

    crud.update_group(
        session=session, db_group=group, group_in=GroupUpdate(calendar_id=calendar.uuid)
    )
    session.refresh(device)

    assert device.config_version == original_version + 1


def test_update_group_label_only_does_not_bump_devices(session: Session) -> None:
    group = crud.create_group(session=session, group_create=GroupCreate(**group_payload()))
    device = crud.create_device(
        session=session, device_create=DeviceCreate(**device_payload(group_id=group.uuid))
    )
    original_version = device.config_version

    crud.update_group(session=session, db_group=group, group_in=GroupUpdate(label="renamed"))
    session.refresh(device)

    assert device.config_version == original_version


def test_update_calendar_weekdays_bumps_devices_of_every_group_using_it(
    session: Session,
) -> None:
    calendar = create_calendar(session)
    group_a = create_group(session, calendar_id=calendar.uuid, label="Group A")
    group_b = create_group(session, calendar_id=calendar.uuid, label="Group B")
    device_a = crud.create_device(
        session=session, device_create=DeviceCreate(**device_payload(group_id=group_a.uuid))
    )
    device_b = crud.create_device(
        session=session, device_create=DeviceCreate(**device_payload(group_id=group_b.uuid))
    )
    version_a = device_a.config_version
    version_b = device_b.config_version

    crud.update_calendar(
        session=session, db_calendar=calendar, calendar_in=CalendarUpdate(weekdays=[6, 7])
    )
    session.refresh(device_a)
    session.refresh(device_b)

    assert device_a.config_version == version_a + 1
    assert device_b.config_version == version_b + 1


def test_update_calendar_label_only_does_not_bump_devices(session: Session) -> None:
    calendar = create_calendar(session)
    group = create_group(session, calendar_id=calendar.uuid)
    device = crud.create_device(
        session=session, device_create=DeviceCreate(**device_payload(group_id=group.uuid))
    )
    original_version = device.config_version

    crud.update_calendar(
        session=session, db_calendar=calendar, calendar_in=CalendarUpdate(label="renamed")
    )
    session.refresh(device)

    assert device.config_version == original_version


def test_create_ignition_preset_bumps_calendar_devices(session: Session) -> None:
    calendar = create_calendar(session)
    group = create_group(session, calendar_id=calendar.uuid)
    device = crud.create_device(
        session=session, device_create=DeviceCreate(**device_payload(group_id=group.uuid))
    )
    original_version = device.config_version

    crud.create_ignition_preset(
        session=session,
        ignition_preset_create=IgnitionPresetCreate(**ignition_preset_payload(calendar.uuid)),
    )
    session.refresh(device)

    assert device.config_version == original_version + 1


def test_update_ignition_preset_bumps_calendar_devices(session: Session) -> None:
    calendar = create_calendar(session)
    group = create_group(session, calendar_id=calendar.uuid)
    device = crud.create_device(
        session=session, device_create=DeviceCreate(**device_payload(group_id=group.uuid))
    )
    preset = create_ignition_preset(session, calendar_id=calendar.uuid)
    original_version = device.config_version

    crud.update_ignition_preset(
        session=session,
        db_ignition_preset=preset,
        ignition_preset_in=IgnitionPresetUpdate(name="renamed"),
    )
    session.refresh(device)

    assert device.config_version == original_version + 1


def test_update_ignition_preset_calendar_move_bumps_both_calendars_devices(
    session: Session,
) -> None:
    calendar_a = create_calendar(session)
    calendar_b = create_calendar(session)
    group_a = create_group(session, calendar_id=calendar_a.uuid, label="Group A")
    group_b = create_group(session, calendar_id=calendar_b.uuid, label="Group B")
    device_a = crud.create_device(
        session=session, device_create=DeviceCreate(**device_payload(group_id=group_a.uuid))
    )
    device_b = crud.create_device(
        session=session, device_create=DeviceCreate(**device_payload(group_id=group_b.uuid))
    )
    preset = create_ignition_preset(session, calendar_id=calendar_a.uuid)
    version_a = device_a.config_version
    version_b = device_b.config_version

    crud.update_ignition_preset(
        session=session,
        db_ignition_preset=preset,
        ignition_preset_in=IgnitionPresetUpdate(calendar_id=calendar_b.uuid),
    )
    session.refresh(device_a)
    session.refresh(device_b)

    assert device_a.config_version == version_a + 1
    assert device_b.config_version == version_b + 1


def test_delete_ignition_preset_bumps_calendar_devices(session: Session) -> None:
    calendar = create_calendar(session)
    group = create_group(session, calendar_id=calendar.uuid)
    device = crud.create_device(
        session=session, device_create=DeviceCreate(**device_payload(group_id=group.uuid))
    )
    preset = create_ignition_preset(session, calendar_id=calendar.uuid)
    original_version = device.config_version

    crud.delete_ignition_preset(session=session, db_ignition_preset=preset)
    session.refresh(device)

    assert device.config_version == original_version + 1


def test_get_devices_pending_sync_excludes_synced_devices(session: Session) -> None:
    device = crud.create_device(session=session, device_create=DeviceCreate(**device_payload()))

    crud.mark_device_synced(session=session, device=device, version=device.config_version)

    assert device not in crud.get_devices_pending_sync(session=session)


def test_mark_device_synced_reappears_pending_after_new_bump(session: Session) -> None:
    device = crud.create_device(session=session, device_create=DeviceCreate(**device_payload()))
    crud.mark_device_synced(session=session, device=device, version=device.config_version)

    crud.update_device(session=session, db_device=device, device_in=DeviceUpdate(active=False))

    assert device in crud.get_devices_pending_sync(session=session)
