import uuid
from typing import Any

from sqlmodel import Session

from app.models import Calendar, Group


def create_calendar(session: Session, **overrides: Any) -> Calendar:
    data: dict[str, Any] = {
        "label": "Default calendar",
        "presets": {
            "setup1": {"start_time": "09:15", "end_time": "19:00"},
            "exception": {"start_time": "10:15", "end_time": "11:30"},
        },
        "days": {"lundi": "setup1", "mardi": "setup1"},
    }
    data.update(overrides)
    calendar = Calendar(**data)
    session.add(calendar)
    session.commit()
    session.refresh(calendar)
    return calendar


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
        "presets": {
            "setup1": {"start_time": "09:15", "end_time": "19:00"},
            "exception": {"start_time": "10:15", "end_time": "11:30"},
        },
        "days": {"lundi": "setup1", "mardi": "setup1"},
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
