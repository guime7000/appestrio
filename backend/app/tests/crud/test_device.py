import uuid

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from app import crud
from app.models import LORA_TYPE_INDEX, DeviceCreate, DeviceType, DeviceUpdate
from app.tests.utils import create_calendar, create_group, device_payload


def test_create_device(session: Session) -> None:
    device_in = DeviceCreate(**device_payload())
    device = crud.create_device(session=session, device_create=device_in)

    assert device.uuid is not None
    assert device.device_id == f"{device_in.device_type.value}{device_in.device_number}"
    assert device.device_name == device_in.device_name
    assert device.active is True
    assert device.is_master is False
    assert device.created_at is not None
    assert device.updated_at is not None


def test_lora_type_index_matches_legacy_and_burger_convention() -> None:
    # Pins the mapping so it can never silently invert (e.g. via a future
    # DeviceType reorder or a switch to enum-position derivation) --
    # legacy's LoraDeviceType.Relaystrio=0/Lumestrio=1, also hardcoded in
    # burger's firmware.
    assert LORA_TYPE_INDEX[DeviceType.RELAYSTRIO] == 0
    assert LORA_TYPE_INDEX[DeviceType.LUMESTRIO] == 1


def test_device_id_is_composed_from_type_and_number(session: Session) -> None:
    device_in = DeviceCreate(**device_payload(device_type="relaystrio", device_number=7))

    device = crud.create_device(session=session, device_create=device_in)

    assert device.device_id == "relaystrio7"


def test_device_update_cannot_change_device_id(session: Session) -> None:
    device = crud.create_device(
        session=session, device_create=DeviceCreate(**device_payload())
    )
    original_device_id = device.device_id

    updated = crud.update_device(
        session=session,
        db_device=device,
        # DeviceUpdate has no device_id field, so this extra key is dropped
        # by pydantic before crud.update_device ever sees it.
        device_in=DeviceUpdate.model_validate({"device_id": "somethingelse"}),
    )

    assert updated.device_id == original_device_id


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


def test_only_one_device_can_be_master(session: Session) -> None:
    crud.create_device(
        session=session, device_create=DeviceCreate(**device_payload(is_master=True))
    )

    with pytest.raises(IntegrityError):
        crud.create_device(
            session=session, device_create=DeviceCreate(**device_payload(is_master=True))
        )


def test_multiple_devices_can_be_non_master(session: Session) -> None:
    crud.create_device(
        session=session, device_create=DeviceCreate(**device_payload(is_master=False))
    )
    crud.create_device(
        session=session, device_create=DeviceCreate(**device_payload(is_master=False))
    )


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


def test_get_free_device_numbers_excludes_used_numbers(session: Session) -> None:
    crud.create_device(
        session=session,
        device_create=DeviceCreate(
            **device_payload(device_type="lumestrio", device_number=0)
        ),
    )
    crud.create_device(
        session=session,
        device_create=DeviceCreate(
            **device_payload(device_type="relaystrio", device_number=5)
        ),
    )

    free_numbers = crud.get_free_device_numbers(session=session)

    assert 0 not in free_numbers[DeviceType.LUMESTRIO]
    assert 1 in free_numbers[DeviceType.LUMESTRIO]
    assert 5 not in free_numbers[DeviceType.RELAYSTRIO]
    assert 0 in free_numbers[DeviceType.RELAYSTRIO]


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
    assert public.calendar.weekdays == calendar.weekdays
