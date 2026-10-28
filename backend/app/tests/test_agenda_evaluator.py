from datetime import datetime

from sqlmodel import Session

from app import crud
from app.models import Device, DeviceCreate, DeviceType
from app.services import agenda_evaluator
from app.tests.utils import create_calendar, create_group, create_ignition_preset

# A fixed Wednesday (ISO weekday 3).
_WEDNESDAY = datetime(2026, 1, 7, 12, 0)


def _make_device(session: Session, **overrides) -> Device:
    payload = {
        "device_number": 3,
        "device_name": "Lumestrio 3",
        "device_type": "lumestrio",
        "active": False,
        "handles_audio": True,
        "handles_dmx": False,
    }
    payload.update(overrides)
    device_create = DeviceCreate(
        device_number=payload.pop("device_number"),
        device_name=payload.pop("device_name"),
        device_type=DeviceType(payload.pop("device_type")),
        active=payload.pop("active"),
        handles_audio=payload.pop("handles_audio"),
        handles_dmx=payload.pop("handles_dmx"),
        **payload,
    )
    return crud.create_device(session=session, device_create=device_create)


def test_resolve_own_device_returns_none_when_no_devices(session: Session) -> None:
    assert agenda_evaluator.resolve_own_device(session) is None


def test_resolve_own_device_returns_the_only_device(session: Session) -> None:
    device = _make_device(session)
    assert agenda_evaluator.resolve_own_device(session).uuid == device.uuid


def test_resolve_own_device_returns_none_when_multiple_devices(session: Session) -> None:
    _make_device(session, device_number=3)
    _make_device(session, device_number=4)
    assert agenda_evaluator.resolve_own_device(session) is None


def test_compute_desired_active_true_within_weekday_date_and_time(session: Session) -> None:
    calendar = create_calendar(session, weekdays=[3])  # Wednesday
    create_ignition_preset(
        session,
        calendar.uuid,
        start_date="01/01/2026",
        stop_date="31/01/2026",
        start_time="09:00",
        stop_time="20:00",
    )
    group = create_group(session, calendar_id=calendar.uuid)
    device = _make_device(session, group_id=group.uuid)
    session.refresh(device)

    assert agenda_evaluator.compute_desired_active(device, now=_WEDNESDAY) is True


def test_compute_desired_active_false_when_weekday_not_in_calendar(session: Session) -> None:
    calendar = create_calendar(session, weekdays=[1, 2])  # Mon/Tue only
    create_ignition_preset(
        session,
        calendar.uuid,
        start_date="01/01/2026",
        stop_date="31/01/2026",
        start_time="09:00",
        stop_time="20:00",
    )
    group = create_group(session, calendar_id=calendar.uuid)
    device = _make_device(session, group_id=group.uuid)
    session.refresh(device)

    assert agenda_evaluator.compute_desired_active(device, now=_WEDNESDAY) is False


def test_compute_desired_active_false_outside_date_range(session: Session) -> None:
    calendar = create_calendar(session, weekdays=[3])
    create_ignition_preset(
        session,
        calendar.uuid,
        start_date="01/06/2026",
        stop_date="30/06/2026",
        start_time="09:00",
        stop_time="20:00",
    )
    group = create_group(session, calendar_id=calendar.uuid)
    device = _make_device(session, group_id=group.uuid)
    session.refresh(device)

    assert agenda_evaluator.compute_desired_active(device, now=_WEDNESDAY) is False


def test_compute_desired_active_false_outside_time_range(session: Session) -> None:
    calendar = create_calendar(session, weekdays=[3])
    create_ignition_preset(
        session,
        calendar.uuid,
        start_date="01/01/2026",
        stop_date="31/01/2026",
        start_time="22:00",
        stop_time="23:00",
    )
    group = create_group(session, calendar_id=calendar.uuid)
    device = _make_device(session, group_id=group.uuid)
    session.refresh(device)

    assert agenda_evaluator.compute_desired_active(device, now=_WEDNESDAY) is False


def test_compute_desired_active_false_with_no_group(session: Session) -> None:
    device = _make_device(session)
    assert agenda_evaluator.compute_desired_active(device, now=_WEDNESDAY) is False


def test_compute_desired_active_false_with_group_but_no_calendar(session: Session) -> None:
    group = create_group(session)
    device = _make_device(session, group_id=group.uuid)
    session.refresh(device)
    assert agenda_evaluator.compute_desired_active(device, now=_WEDNESDAY) is False


def test_evaluate_once_turns_device_on_and_calls_apply_active_state(
    session: Session, monkeypatch
) -> None:
    calls = []
    monkeypatch.setattr(
        agenda_evaluator, "apply_active_state", lambda **kwargs: calls.append(kwargs)
    )
    calendar = create_calendar(session, weekdays=[3])
    create_ignition_preset(
        session,
        calendar.uuid,
        start_date="01/01/2026",
        stop_date="31/01/2026",
        start_time="09:00",
        stop_time="20:00",
    )
    group = create_group(session, calendar_id=calendar.uuid)
    device = _make_device(session, group_id=group.uuid, active=False)
    session.refresh(device)

    agenda_evaluator.evaluate_once(session, now=_WEDNESDAY)

    session.refresh(device)
    assert device.active is True
    assert calls == [
        {
            "device_id": device.device_id,
            "active": True,
            "handles_audio": True,
            "handles_dmx": False,
            "audiofile": None,
        }
    ]


def test_evaluate_once_does_not_bump_config_version(session: Session, monkeypatch) -> None:
    monkeypatch.setattr(agenda_evaluator, "apply_active_state", lambda **kwargs: None)
    calendar = create_calendar(session, weekdays=[3])
    create_ignition_preset(
        session,
        calendar.uuid,
        start_date="01/01/2026",
        stop_date="31/01/2026",
        start_time="09:00",
        stop_time="20:00",
    )
    group = create_group(session, calendar_id=calendar.uuid)
    device = _make_device(session, group_id=group.uuid, active=False)
    session.refresh(device)
    config_version_before = device.config_version

    agenda_evaluator.evaluate_once(session, now=_WEDNESDAY)

    session.refresh(device)
    assert device.config_version == config_version_before


def test_evaluate_once_is_noop_when_state_unchanged(session: Session, monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(
        agenda_evaluator, "apply_active_state", lambda **kwargs: calls.append(kwargs)
    )
    _make_device(session, active=False)  # no group/calendar -> stays off

    agenda_evaluator.evaluate_once(session, now=_WEDNESDAY)

    assert calls == []


def test_evaluate_once_is_noop_when_agenda_disabled(session: Session, monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(
        agenda_evaluator, "apply_active_state", lambda **kwargs: calls.append(kwargs)
    )
    calendar = create_calendar(session, weekdays=[3])
    create_ignition_preset(
        session,
        calendar.uuid,
        start_date="01/01/2026",
        stop_date="31/01/2026",
        start_time="09:00",
        stop_time="20:00",
    )
    group = create_group(session, calendar_id=calendar.uuid)
    device = _make_device(session, group_id=group.uuid, active=False)
    session.refresh(device)
    agenda_evaluator.set_agenda_disabled(True)
    try:
        agenda_evaluator.evaluate_once(session, now=_WEDNESDAY)
        session.refresh(device)
        assert device.active is False
        assert calls == []
    finally:
        agenda_evaluator.set_agenda_disabled(False)


def test_set_and_is_agenda_disabled_roundtrip() -> None:
    agenda_evaluator.set_agenda_disabled(True)
    try:
        assert agenda_evaluator.is_agenda_disabled() is True
    finally:
        agenda_evaluator.set_agenda_disabled(False)
    assert agenda_evaluator.is_agenda_disabled() is False
