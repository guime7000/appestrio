import uuid

from sqlmodel import Session

from app import crud
from app.models import DeviceCreate, GroupCreate, GroupUpdate
from app.tests.utils import create_calendar, device_payload, group_payload


def test_create_group(session: Session) -> None:
    group_in = GroupCreate(**group_payload())
    group = crud.create_group(session=session, group_create=group_in)

    assert group.uuid is not None
    assert group.label == group_in.label
    assert group.calendar_id is None
    assert group.created_at is not None
    assert group.updated_at is not None


def test_create_group_with_calendar(session: Session) -> None:
    calendar = create_calendar(session)

    group = crud.create_group(
        session=session,
        group_create=GroupCreate(**group_payload(calendar_id=calendar.uuid)),
    )

    assert group.calendar_id == calendar.uuid


def test_get_group(session: Session) -> None:
    group = crud.create_group(
        session=session, group_create=GroupCreate(**group_payload())
    )

    fetched = crud.get_group(session=session, group_uuid=group.uuid)

    assert fetched is not None
    assert fetched.uuid == group.uuid


def test_get_group_not_found(session: Session) -> None:
    assert crud.get_group(session=session, group_uuid=uuid.uuid4()) is None


def test_get_groups_pagination(session: Session) -> None:
    for _ in range(3):
        crud.create_group(session=session, group_create=GroupCreate(**group_payload()))

    groups, count = crud.get_groups(session=session, skip=0, limit=2)

    assert count == 3
    assert len(groups) == 2


def test_update_group_partial(session: Session) -> None:
    group = crud.create_group(
        session=session, group_create=GroupCreate(**group_payload(label="Group A"))
    )
    original_updated_at = group.updated_at
    calendar = create_calendar(session)

    updated = crud.update_group(
        session=session,
        db_group=group,
        group_in=GroupUpdate(calendar_id=calendar.uuid),
    )

    assert updated.calendar_id == calendar.uuid
    # Untouched fields keep their value: PATCH is partial.
    assert updated.label == "Group A"
    assert updated.updated_at >= original_updated_at


def test_delete_group(session: Session) -> None:
    group = crud.create_group(
        session=session, group_create=GroupCreate(**group_payload())
    )

    crud.delete_group(session=session, db_group=group)

    assert crud.get_group(session=session, group_uuid=group.uuid) is None


def test_group_devices_relationship(session: Session) -> None:
    group = crud.create_group(
        session=session, group_create=GroupCreate(**group_payload())
    )
    crud.create_device(
        session=session,
        device_create=DeviceCreate(**device_payload(group_id=group.uuid)),
    )

    session.refresh(group)

    assert len(group.devices) == 1


def test_set_group_devices(session: Session) -> None:
    group = crud.create_group(
        session=session, group_create=GroupCreate(**group_payload())
    )
    device = crud.create_device(
        session=session, device_create=DeviceCreate(**device_payload())
    )

    updated = crud.set_group_devices(
        session=session, db_group=group, device_uuids=[device.uuid]
    )

    assert [d.uuid for d in updated.devices] == [device.uuid]
    session.refresh(device)
    assert device.group_id == group.uuid


def test_set_group_devices_unassigns_removed_devices(session: Session) -> None:
    group = crud.create_group(
        session=session, group_create=GroupCreate(**group_payload())
    )
    device = crud.create_device(
        session=session,
        device_create=DeviceCreate(**device_payload(group_id=group.uuid)),
    )

    crud.set_group_devices(session=session, db_group=group, device_uuids=[])

    session.refresh(device)
    assert device.group_id is None


def test_set_group_devices_not_found(session: Session) -> None:
    group = crud.create_group(
        session=session, group_create=GroupCreate(**group_payload())
    )
    missing_uuid = uuid.uuid4()

    try:
        crud.set_group_devices(
            session=session, db_group=group, device_uuids=[missing_uuid]
        )
        raised = False
    except crud.DeviceNotFoundError as exc:
        raised = True
        assert exc.missing_uuids == [missing_uuid]

    assert raised
