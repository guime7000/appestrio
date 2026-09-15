import uuid

from fastapi import APIRouter, HTTPException
from sqlalchemy.exc import IntegrityError

from app import crud
from app.api.deps import SessionDep
from app.models import (
    Device,
    DeviceBulkDeleteRequest,
    DeviceCreate,
    DevicePublic,
    DevicesPublic,
    DeviceType,
    DeviceUpdate,
    FreeDeviceNumbers,
    Group,
    Message,
)

router = APIRouter(prefix="/devices", tags=["devices"])


def _get_device_or_404(session: SessionDep, device_id: str) -> Device:
    device = crud.get_device_by_device_id(session=session, device_id=device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return device


def _check_group_exists(session: SessionDep, group_id: uuid.UUID | None) -> None:
    if group_id is not None and not session.get(Group, group_id):
        raise HTTPException(status_code=404, detail="Group not found")


def _conflict_detail(error: IntegrityError) -> str:
    if "is_master" in str(error.orig):
        return "Another device is already the master"
    return "A device with this device_id already exists"


@router.get("/", response_model=DevicesPublic)
def list_devices(session: SessionDep, skip: int = 0, limit: int = 100) -> DevicesPublic:
    devices, count = crud.get_devices(session=session, skip=skip, limit=limit)
    return DevicesPublic(
        data=[crud.device_to_public(device) for device in devices], count=count
    )


@router.get("/free_devices_id", response_model=FreeDeviceNumbers)
def get_free_devices_id(session: SessionDep) -> FreeDeviceNumbers:
    free_numbers = crud.get_free_device_numbers(session=session)
    return FreeDeviceNumbers(
        relaystrio=free_numbers[DeviceType.RELAYSTRIO],
        lumestrio=free_numbers[DeviceType.LUMESTRIO],
    )


@router.get("/{device_id}", response_model=DevicePublic)
def get_device(session: SessionDep, device_id: str) -> DevicePublic:
    device = _get_device_or_404(session, device_id)
    return crud.device_to_public(device)


@router.post("/", response_model=DevicePublic, status_code=201)
def create_device(session: SessionDep, device_in: DeviceCreate) -> DevicePublic:
    _check_group_exists(session, device_in.group_id)
    try:
        device = crud.create_device(session=session, device_create=device_in)
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail=_conflict_detail(exc))
    return crud.device_to_public(device)


@router.patch("/{device_id}", response_model=DevicePublic)
def update_device(
    session: SessionDep, device_id: str, device_in: DeviceUpdate
) -> DevicePublic:
    device = _get_device_or_404(session, device_id)
    _check_group_exists(session, device_in.group_id)
    try:
        device = crud.update_device(session=session, db_device=device, device_in=device_in)
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail=_conflict_detail(exc))
    return crud.device_to_public(device)


@router.delete("/", response_model=Message)
def delete_devices(session: SessionDep, payload: DeviceBulkDeleteRequest) -> Message:
    devices = crud.get_devices_by_device_ids(session=session, device_ids=payload.device_ids)
    missing = set(payload.device_ids) - {device.device_id for device in devices}
    if missing:
        raise HTTPException(
            status_code=404,
            detail=f"Device(s) not found: {', '.join(sorted(missing))}",
        )
    crud.delete_devices(session=session, db_devices=devices)
    return Message(message=f"{len(devices)} device(s) deleted successfully")
