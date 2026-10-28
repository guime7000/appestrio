import pytest
from sqlmodel import Session

from app import crud
from app.services import device_bootstrap


def test_bootstrap_creates_device_when_hostname_matches(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LORA_HOSTNAME", "lumestrio0")

    device = device_bootstrap.bootstrap_own_device(session)

    assert device is not None
    assert device.device_id == "lumestrio0"
    assert device.is_master is True


def test_bootstrap_is_none_when_hostname_does_not_match(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LORA_HOSTNAME", "raspberrypi")

    device = device_bootstrap.bootstrap_own_device(session)

    assert device is None
    assert crud.get_master_device(session=session) is None


def test_bootstrap_returns_none_on_conflict(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.models import DeviceCreate, DeviceType

    monkeypatch.setenv("LORA_HOSTNAME", "lumestrio0")
    crud.create_device(
        session=session,
        device_create=DeviceCreate(
            device_number=5,
            device_name="Some other master",
            device_type=DeviceType.LUMESTRIO,
            is_master=True,
        ),
    )

    device = device_bootstrap.bootstrap_own_device(session)

    assert device is None
