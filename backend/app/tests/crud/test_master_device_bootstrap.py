from sqlmodel import Session

from app import crud
from app.models import DeviceType
from app.tests.utils import device_payload


def test_ensure_own_master_device_creates_new_row(session: Session) -> None:
    device = crud.ensure_own_master_device(
        session=session, device_type=DeviceType.LUMESTRIO, device_number=0
    )

    assert device.device_id == "lumestrio0"
    assert device.is_master is True
    assert device.active is True


def test_ensure_own_master_device_is_idempotent(session: Session) -> None:
    first = crud.ensure_own_master_device(
        session=session, device_type=DeviceType.LUMESTRIO, device_number=0
    )
    second = crud.ensure_own_master_device(
        session=session, device_type=DeviceType.LUMESTRIO, device_number=0
    )

    assert first.uuid == second.uuid
    assert crud.get_devices(session=session, skip=0, limit=100)[1] == 1


def test_ensure_own_master_device_flags_existing_row(session: Session) -> None:
    device_in = crud.DeviceCreate(**device_payload(device_number=0, is_master=False))
    existing = crud.create_device(session=session, device_create=device_in)
    assert existing.is_master is False

    ensured = crud.ensure_own_master_device(
        session=session, device_type=DeviceType.LUMESTRIO, device_number=0
    )

    assert ensured.uuid == existing.uuid
    assert ensured.is_master is True


def test_ensure_own_master_device_raises_on_conflict(session: Session) -> None:
    other = crud.DeviceCreate(
        **device_payload(device_number=5, is_master=True, device_type="lumestrio")
    )
    crud.create_device(session=session, device_create=other)

    try:
        crud.ensure_own_master_device(
            session=session, device_type=DeviceType.LUMESTRIO, device_number=0
        )
        raise AssertionError("expected MasterDeviceConflictError")
    except crud.MasterDeviceConflictError:
        pass

    assert crud.get_device_by_device_id(session=session, device_id="lumestrio0") is None


def test_get_master_device_returns_none_when_none_flagged(session: Session) -> None:
    assert crud.get_master_device(session=session) is None


def test_get_master_device_finds_flagged_row(session: Session) -> None:
    device = crud.ensure_own_master_device(
        session=session, device_type=DeviceType.LUMESTRIO, device_number=0
    )
    assert crud.get_master_device(session=session).uuid == device.uuid
