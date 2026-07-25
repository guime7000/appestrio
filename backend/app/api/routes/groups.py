import uuid

from fastapi import APIRouter, HTTPException

from app import crud
from app.api.deps import SessionDep
from app.models import (
    Calendar,
    Group,
    GroupCreate,
    GroupPublic,
    GroupsPublic,
    GroupUpdate,
    Message,
)

router = APIRouter(prefix="/groups", tags=["groups"])


def _get_group_or_404(session: SessionDep, group_uuid: uuid.UUID) -> Group:
    group = crud.get_group(session=session, group_uuid=group_uuid)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    return group


def _check_calendar_exists(session: SessionDep, calendar_id: uuid.UUID | None) -> None:
    if calendar_id is not None and not session.get(Calendar, calendar_id):
        raise HTTPException(status_code=404, detail="Calendar not found")


@router.get("/", response_model=GroupsPublic)
def list_groups(session: SessionDep, skip: int = 0, limit: int = 100) -> GroupsPublic:
    groups, count = crud.get_groups(session=session, skip=skip, limit=limit)
    return GroupsPublic(data=groups, count=count)


@router.get("/{group_uuid}", response_model=GroupPublic)
def get_group(session: SessionDep, group_uuid: uuid.UUID) -> Group:
    return _get_group_or_404(session, group_uuid)


@router.post("/", response_model=GroupPublic, status_code=201)
def create_group(session: SessionDep, group_in: GroupCreate) -> Group:
    _check_calendar_exists(session, group_in.calendar_id)
    return crud.create_group(session=session, group_create=group_in)


@router.patch("/{group_uuid}", response_model=GroupPublic)
def update_group(
    session: SessionDep, group_uuid: uuid.UUID, group_in: GroupUpdate
) -> Group:
    group = _get_group_or_404(session, group_uuid)
    _check_calendar_exists(session, group_in.calendar_id)
    return crud.update_group(session=session, db_group=group, group_in=group_in)


@router.delete("/{group_uuid}", response_model=Message)
def delete_group(session: SessionDep, group_uuid: uuid.UUID) -> Message:
    group = _get_group_or_404(session, group_uuid)
    if group.devices:
        raise HTTPException(
            status_code=409,
            detail="Group is still assigned to one or more devices",
        )
    crud.delete_group(session=session, db_group=group)
    return Message(message="Group deleted successfully")
