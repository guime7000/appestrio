import uuid

from fastapi import APIRouter, HTTPException

from app import crud
from app.api.deps import SessionDep
from app.crud import IgnitionPresetDateRangeError, IgnitionPresetOverlapError
from app.models import (
    BulkDeleteRequest,
    Calendar,
    IgnitionPreset,
    IgnitionPresetCreate,
    IgnitionPresetPublic,
    IgnitionPresetsPublic,
    IgnitionPresetUpdate,
    Message,
)

router = APIRouter(prefix="/ignition-presets", tags=["ignition-presets"])


def _get_ignition_preset_or_404(
    session: SessionDep, ignition_preset_uuid: uuid.UUID
) -> IgnitionPreset:
    ignition_preset = crud.get_ignition_preset(
        session=session, ignition_preset_uuid=ignition_preset_uuid
    )
    if not ignition_preset:
        raise HTTPException(status_code=404, detail="Ignition preset not found")
    return ignition_preset


def _check_calendar_exists(session: SessionDep, calendar_id: uuid.UUID) -> None:
    if not session.get(Calendar, calendar_id):
        raise HTTPException(status_code=404, detail="Calendar not found")


@router.get("/", response_model=IgnitionPresetsPublic)
def list_ignition_presets(
    session: SessionDep, skip: int = 0, limit: int = 100
) -> IgnitionPresetsPublic:
    presets, count = crud.get_ignition_presets(session=session, skip=skip, limit=limit)
    return IgnitionPresetsPublic(data=presets, count=count)


@router.get("/{ignition_preset_uuid}", response_model=IgnitionPresetPublic)
def get_ignition_preset(session: SessionDep, ignition_preset_uuid: uuid.UUID) -> IgnitionPreset:
    return _get_ignition_preset_or_404(session, ignition_preset_uuid)


@router.post("/", response_model=IgnitionPresetPublic, status_code=201)
def create_ignition_preset(
    session: SessionDep, ignition_preset_in: IgnitionPresetCreate
) -> IgnitionPreset:
    _check_calendar_exists(session, ignition_preset_in.calendar_id)
    try:
        return crud.create_ignition_preset(
            session=session, ignition_preset_create=ignition_preset_in
        )
    except IgnitionPresetOverlapError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.patch("/{ignition_preset_uuid}", response_model=IgnitionPresetPublic)
def update_ignition_preset(
    session: SessionDep,
    ignition_preset_uuid: uuid.UUID,
    ignition_preset_in: IgnitionPresetUpdate,
) -> IgnitionPreset:
    ignition_preset = _get_ignition_preset_or_404(session, ignition_preset_uuid)
    if ignition_preset_in.calendar_id is not None:
        _check_calendar_exists(session, ignition_preset_in.calendar_id)
    try:
        return crud.update_ignition_preset(
            session=session,
            db_ignition_preset=ignition_preset,
            ignition_preset_in=ignition_preset_in,
        )
    except IgnitionPresetDateRangeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except IgnitionPresetOverlapError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.delete("/", response_model=Message)
def delete_ignition_presets(session: SessionDep, payload: BulkDeleteRequest) -> Message:
    presets = crud.get_ignition_presets_by_uuids(session=session, uuids=payload.uuids)
    missing = set(payload.uuids) - {preset.uuid for preset in presets}
    if missing:
        raise HTTPException(
            status_code=404,
            detail=f"Ignition preset(s) not found: {', '.join(str(u) for u in sorted(missing))}",
        )
    crud.delete_ignition_presets(session=session, db_ignition_presets=presets)
    return Message(message=f"{len(presets)} ignition preset(s) deleted successfully")
