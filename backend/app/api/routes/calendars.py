import uuid

from fastapi import APIRouter, HTTPException

from app import crud
from app.api.deps import SessionDep
from app.models import (
    BulkDeleteRequest,
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


@router.post("/{calendar_uuid}/duplicate", response_model=CalendarPublic, status_code=201)
def duplicate_calendar(session: SessionDep, calendar_uuid: uuid.UUID) -> Calendar:
    calendar = _get_calendar_or_404(session, calendar_uuid)
    return crud.duplicate_calendar(session=session, db_calendar=calendar)


@router.patch("/{calendar_uuid}", response_model=CalendarPublic)
def update_calendar(
    session: SessionDep, calendar_uuid: uuid.UUID, calendar_in: CalendarUpdate
) -> Calendar:
    calendar = _get_calendar_or_404(session, calendar_uuid)
    return crud.update_calendar(
        session=session, db_calendar=calendar, calendar_in=calendar_in
    )


@router.delete("/", response_model=Message)
def delete_calendars(session: SessionDep, payload: BulkDeleteRequest) -> Message:
    calendars = crud.get_calendars_by_uuids(session=session, uuids=payload.uuids)
    missing = set(payload.uuids) - {calendar.uuid for calendar in calendars}
    if missing:
        raise HTTPException(
            status_code=404,
            detail=f"Calendar(s) not found: {', '.join(str(u) for u in sorted(missing))}",
        )
    in_use = [calendar for calendar in calendars if calendar.groups]
    if in_use:
        raise HTTPException(
            status_code=409,
            detail="Calendar(s) still assigned to one or more groups: "
            + ", ".join(str(calendar.uuid) for calendar in in_use),
        )
    crud.delete_calendars(session=session, db_calendars=calendars)
    return Message(message=f"{len(calendars)} calendar(s) deleted successfully")
