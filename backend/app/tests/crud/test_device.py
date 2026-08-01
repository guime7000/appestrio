import uuid

from sqlmodel import Session

from app import crud
from app.models import DeviceCreate, DeviceUpdate
from app.tests.utils import create_calendar, create_group, device_payload


def test_create_device(session: Session) -> None:
    device_in = DeviceCreate(**device_payload())
    device = crud.create_device(session=session, device_create=device_in)

    assert device.uuid is not None
    assert device.device_id == device_in.device_id
    assert device.device_name == device_in.device_name
    assert device.active is True
    assert device.created_at is not None
    assert device.updated_at is not None


def test_get_device(session: Session) -> None:
    device = crud.create_device(
        session=session, device_create=DeviceCreate(**device_payload())
    )

    fetched = crud.get_device(session=session, device_uuid=device.uuid)

    assert fetched is not None
    assert fetched.uuid == device.uuid


def test_get_device_not_found(session: Session) -> None:
    assert crud.get_device(session=session, device_uuid=uuid.uuid4()) is None


def test_get_devices_pagination(session: Session) -> None:
    for _ in range(3):
        crud.create_device(session=session, device_create=DeviceCreate(**device_payload()))

    devices, count = crud.get_devices(session=session, skip=0, limit=2)

    assert count == 3
    assert len(devices) == 2


def test_update_device_partial(session: Session) -> None:
    device = crud.create_device(
        session=session, device_create=DeviceCreate(**device_payload())
    )
    original_device_name = device.device_name
    original_updated_at = device.updated_at

    updated = crud.update_device(
        session=session,
        db_device=device,
        device_in=DeviceUpdate(audiofile="new_audio.mp3"),
    )

    assert updated.audiofile == "new_audio.mp3"
    # Untouched fields keep their value: PATCH is partial.
    assert updated.device_name == original_device_name
    assert updated.updated_at >= original_updated_at


def test_delete_device(session: Session) -> None:
    device = crud.create_device(
        session=session, device_create=DeviceCreate(**device_payload())
    )

    crud.delete_device(session=session, db_device=device)

    assert crud.get_device(session=session, device_uuid=device.uuid) is None


def test_device_to_public_without_group(session: Session) -> None:
    device = crud.create_device(
        session=session, device_create=DeviceCreate(**device_payload())
    )

    public = crud.device_to_public(device)

    assert public.group is None
    assert public.group_id is None
    assert public.calendar is None


def test_device_to_public_with_group_and_calendar(session: Session) -> None:
    calendar = create_calendar(session)
    group = create_group(session, calendar_id=calendar.uuid, label="group A")
    device = crud.create_device(
        session=session,
        device_create=DeviceCreate(**device_payload(group_id=group.uuid)),
    )
    session.refresh(device)

    public = crud.device_to_public(device)

    assert public.group == "group A"
    assert public.group_id == group.uuid
    assert public.calendar is not None
    assert public.calendar.uuid == calendar.uuid
    assert public.calendar.presets == calendar.presets
