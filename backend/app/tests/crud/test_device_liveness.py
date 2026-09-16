from sqlmodel import Session

from app import crud
from app.models import DeviceCreate
from app.tests.utils import device_payload


def test_new_device_has_no_liveness_data_yet(session: Session) -> None:
    device = crud.create_device(session=session, device_create=DeviceCreate(**device_payload()))

    assert device.last_seen is None
    assert device.last_roundtrip_ms is None


def test_record_device_seen_sets_last_seen_and_roundtrip(session: Session) -> None:
    device = crud.create_device(session=session, device_create=DeviceCreate(**device_payload()))

    updated = crud.record_device_seen(session=session, device=device, roundtrip_ms=123)

    assert updated.last_seen is not None
    assert updated.last_roundtrip_ms == 123


def test_record_device_seen_without_roundtrip(session: Session) -> None:
    device = crud.create_device(session=session, device_create=DeviceCreate(**device_payload()))

    updated = crud.record_device_seen(session=session, device=device)

    assert updated.last_seen is not None
    assert updated.last_roundtrip_ms is None


def test_record_device_seen_updates_last_seen_on_each_call(session: Session) -> None:
    device = crud.create_device(session=session, device_create=DeviceCreate(**device_payload()))

    first = crud.record_device_seen(session=session, device=device, roundtrip_ms=200)
    first_seen = first.last_seen
    second = crud.record_device_seen(session=session, device=device, roundtrip_ms=50)

    assert second.last_roundtrip_ms == 50
    assert second.last_seen >= first_seen
