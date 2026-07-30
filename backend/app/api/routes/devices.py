import uuid

from fastapi import APIRouter, HTTPException
from sqlalchemy.exc import IntegrityError

from app import crud
from app.api.deps import SessionDep
from app.models import (
    BulkDeleteRequest,
    Device,
    DeviceCreate,
    DevicePublic,
    DevicesPublic,
    DeviceUpdate,
    Group,
    Message,
)

router = APIRouter(prefix="/devices", tags=["devices"])


def _get_device_or_404(session: SessionDep, device_uuid: uuid.UUID) -> Device:
    device = crud.get_device(session=session, device_uuid=device_uuid)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return device


def _check_group_exists(session: SessionDep, group_id: uuid.UUID | None) -> None:
    if group_id is not None and not session.get(Group, group_id):
        raise HTTPException(status_code=404, detail="Group not found")


@router.get("/", response_model=DevicesPublic)
def list_devices(session: SessionDep, skip: int = 0, limit: int = 100) -> DevicesPublic:
    devices, count = crud.get_devices(session=session, skip=skip, limit=limit)
    return DevicesPublic(
        data=[crud.device_to_public(device) for device in devices], count=count
    )


@router.get("/{device_uuid}", response_model=DevicePublic)
def get_device(session: SessionDep, device_uuid: uuid.UUID) -> DevicePublic:
    device = _get_device_or_404(session, device_uuid)
    return crud.device_to_public(device)


@router.post("/", response_model=DevicePublic, status_code=201)
def create_device(session: SessionDep, device_in: DeviceCreate) -> DevicePublic:
    _check_group_exists(session, device_in.group_id)
    try:
        device = crud.create_device(session=session, device_create=device_in)
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=409, detail="A device with this device_id already exists"
        )
    return crud.device_to_public(device)


@router.patch("/{device_uuid}", response_model=DevicePublic)
def update_device(
    session: SessionDep, device_uuid: uuid.UUID, device_in: DeviceUpdate
) -> DevicePublic:
    device = _get_device_or_404(session, device_uuid)
    _check_group_exists(session, device_in.group_id)
    try:
        device = crud.update_device(session=session, db_device=device, device_in=device_in)
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=409, detail="A device with this device_id already exists"
        )
    return crud.device_to_public(device)


@router.delete("/{device_uuid}", response_model=Message)
def delete_device(session: SessionDep, device_uuid: uuid.UUID) -> Message:
    device = _get_device_or_404(session, device_uuid)
    crud.delete_device(session=session, db_device=device)
    return Message(message="Device deleted successfully")


@router.delete("/", response_model=Message)
def delete_devices(session: SessionDep, payload: BulkDeleteRequest) -> Message:
    devices = crud.get_devices_by_uuids(session=session, uuids=payload.uuids)
    missing = set(payload.uuids) - {device.uuid for device in devices}
    if missing:
        raise HTTPException(
            status_code=404,
            detail=f"Device(s) not found: {', '.join(str(u) for u in sorted(missing))}",
        )
    crud.delete_devices(session=session, db_devices=devices)
    return Message(message=f"{len(devices)} device(s) deleted successfully")
