import uuid

from sqlmodel import Session

from app import crud
from app.models import CalendarCreate, CalendarUpdate
from app.tests.utils import calendar_payload, create_group


def test_create_calendar(session: Session) -> None:
    calendar_in = CalendarCreate(**calendar_payload())
    calendar = crud.create_calendar(session=session, calendar_create=calendar_in)

    assert calendar.uuid is not None
    assert calendar.label == calendar_in.label
    assert calendar.presets == calendar_in.presets
    assert calendar.days == calendar_in.days
    assert calendar.created_at is not None
    assert calendar.updated_at is not None


def test_get_calendar(session: Session) -> None:
    calendar = crud.create_calendar(
        session=session, calendar_create=CalendarCreate(**calendar_payload())
    )

    fetched = crud.get_calendar(session=session, calendar_uuid=calendar.uuid)

    assert fetched is not None
    assert fetched.uuid == calendar.uuid


def test_get_calendar_not_found(session: Session) -> None:
    assert crud.get_calendar(session=session, calendar_uuid=uuid.uuid4()) is None


def test_get_calendars_pagination(session: Session) -> None:
    for _ in range(3):
        crud.create_calendar(
            session=session, calendar_create=CalendarCreate(**calendar_payload())
        )

    calendars, count = crud.get_calendars(session=session, skip=0, limit=2)

    assert count == 3
    assert len(calendars) == 2


def test_update_calendar_partial(session: Session) -> None:
    calendar = crud.create_calendar(
        session=session, calendar_create=CalendarCreate(**calendar_payload())
    )
    original_label = calendar.label
    original_updated_at = calendar.updated_at

    updated = crud.update_calendar(
        session=session,
        db_calendar=calendar,
        calendar_in=CalendarUpdate(days={"lundi": "exception"}),
    )

    assert updated.days == {"lundi": "exception"}
    # Untouched fields keep their value: PATCH is partial.
    assert updated.label == original_label
    assert updated.updated_at >= original_updated_at


def test_delete_calendar(session: Session) -> None:
    calendar = crud.create_calendar(
        session=session, calendar_create=CalendarCreate(**calendar_payload())
    )

    crud.delete_calendar(session=session, db_calendar=calendar)

    assert crud.get_calendar(session=session, calendar_uuid=calendar.uuid) is None


def test_calendar_groups_relationship(session: Session) -> None:
    calendar = crud.create_calendar(
        session=session, calendar_create=CalendarCreate(**calendar_payload())
    )
    create_group(session, calendar_id=calendar.uuid)

    session.refresh(calendar)

    assert len(calendar.groups) == 1
