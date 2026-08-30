import uuid
from typing import Any

from sqlmodel import Session

from app.models import Calendar, Group, IgnitionPreset


def create_calendar(session: Session, **overrides: Any) -> Calendar:
    data: dict[str, Any] = {
        "label": "Default calendar",
        "weekdays": [1, 2, 3, 4, 5],
    }
    data.update(overrides)
    calendar = Calendar(**data)
    session.add(calendar)
    session.commit()
    session.refresh(calendar)
    return calendar


def create_ignition_preset(
    session: Session, calendar_id: uuid.UUID, **overrides: Any
) -> IgnitionPreset:
    data: dict[str, Any] = {
        "name": "Default preset",
        "description": "A default ignition preset",
        "start_date": "01/01/2026",
        "stop_date": "31/01/2026",
        "start_time": "09:15",
        "stop_time": "19:00",
        "calendar_id": calendar_id,
    }
    data.update(overrides)
    ignition_preset = IgnitionPreset(**data)
    session.add(ignition_preset)
    session.commit()
    session.refresh(ignition_preset)
    return ignition_preset


def create_group(
    session: Session, calendar_id: uuid.UUID | None = None, **overrides: Any
) -> Group:
    data: dict[str, Any] = {"label": "Group A", "calendar_id": calendar_id}
    data.update(overrides)
    group = Group(**data)
    session.add(group)
    session.commit()
    session.refresh(group)
    return group


def calendar_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "label": "Default calendar",
        "weekdays": [1, 2, 3, 4, 5],
    }
    payload.update(overrides)
    return payload


def ignition_preset_payload(calendar_id: uuid.UUID | str, **overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "name": "Default preset",
        "description": "A default ignition preset",
        "start_date": "01/01/2026",
        "stop_date": "31/01/2026",
        "start_time": "09:15",
        "stop_time": "19:00",
        "calendar_id": str(calendar_id),
    }
    payload.update(overrides)
    return payload


def group_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"label": "Group A"}
    payload.update(overrides)
    return payload


def device_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "device_id": f"lumestrio-{uuid.uuid4().hex[:8]}",
        "device_name": "Le 13e lumestrio",
        "device_type": "lumestrio",
        "active": True,
        "audiofile": "the audio.mp3",
        "ip": "127.0.0.13",
        "master_ip": "127.0.0.1",
    }
    payload.update(overrides)
    return payload
