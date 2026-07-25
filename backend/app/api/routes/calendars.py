import uuid

from fastapi import APIRouter, HTTPException

from app import crud
from app.api.deps import SessionDep
from app.models import (
    Calendar,
    CalendarCreate,
    CalendarPublic,
    CalendarsPublic,
    CalendarUpdate,
    Message,
)

router = APIRouter(prefix="/calendars", tags=["calendars"])


def _get_calendar_or_404(session: SessionDep, calendar_uuid: uuid.UUID) -> Calendar:
    calendar = crud.get_calendar(session=session, calendar_uuid=calendar_uuid)
    if not calendar:
        raise HTTPException(status_code=404, detail="Calendar not found")
    return calendar


@router.get("/", response_model=CalendarsPublic)
def list_calendars(
    session: SessionDep, skip: int = 0, limit: int = 100
) -> CalendarsPublic:
    calendars, count = crud.get_calendars(session=session, skip=skip, limit=limit)
    return CalendarsPublic(data=calendars, count=count)


@router.get("/{calendar_uuid}", response_model=CalendarPublic)
def get_calendar(session: SessionDep, calendar_uuid: uuid.UUID) -> Calendar:
    return _get_calendar_or_404(session, calendar_uuid)


@router.post("/", response_model=CalendarPublic, status_code=201)
def create_calendar(session: SessionDep, calendar_in: CalendarCreate) -> Calendar:
    return crud.create_calendar(session=session, calendar_create=calendar_in)


@router.patch("/{calendar_uuid}", response_model=CalendarPublic)
def update_calendar(
    session: SessionDep, calendar_uuid: uuid.UUID, calendar_in: CalendarUpdate
) -> Calendar:
    calendar = _get_calendar_or_404(session, calendar_uuid)
    return crud.update_calendar(
        session=session, db_calendar=calendar, calendar_in=calendar_in
    )


@router.delete("/{calendar_uuid}", response_model=Message)
def delete_calendar(session: SessionDep, calendar_uuid: uuid.UUID) -> Message:
    calendar = _get_calendar_or_404(session, calendar_uuid)
    if calendar.groups:
        raise HTTPException(
            status_code=409,
            detail="Calendar is still assigned to one or more groups",
        )
    crud.delete_calendar(session=session, db_calendar=calendar)
    return Message(message="Calendar deleted successfully")
