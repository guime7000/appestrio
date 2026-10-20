import uuid

from fastapi import APIRouter, HTTPException

from app import crud
from app.api.deps import SessionDep
from app.models import (
    BulkDeleteRequest,
    Calendar,
    DevicesPublic,
    DeviceType,
    Group,
    GroupCreate,
    GroupDevicesUpdate,
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


@router.patch("/{group_uuid}/devices", response_model=DevicesPublic)
def set_group_devices(
    session: SessionDep, group_uuid: uuid.UUID, devices_in: GroupDevicesUpdate
) -> DevicesPublic:
    group = _get_group_or_404(session, group_uuid)
    try:
        group = crud.set_group_devices(
            session=session, db_group=group, device_ids=devices_in.device_ids
        )
    except crud.DeviceNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Device(s) not found: {', '.join(exc.missing_device_ids)}",
        )
    return DevicesPublic(
        data=[crud.device_to_public(device) for device in group.devices],
        count=len(group.devices),
    )


@router.post("/{group_uuid}/test-calendar", response_model=Message)
def test_calendar(session: SessionDep, group_uuid: uuid.UUID) -> Message:
    """Checks whether every lumestrio device in the group is actually in
    sync with master -- what "Test calendrier" (GroupsView.vue) means: a
    verification, not a trigger. `config_version` is master's
    authoritative "current desired config" counter; `synced_version` is
    the last value lora-daemon has confirmed the device actually applied
    (from a real PONG, not just "a push was sent") -- see crud.py's
    `mark_device_synced` for why that distinction matters. The two
    matching is the actual proof a device is in sync; nothing is pushed
    or triggered here, this only reads the already-shared DB state.
    relaystrio members are reported separately since config-sync isn't
    implemented for them at all yet (item 4 in To_Be_Done.md) -- the
    comparison wouldn't mean anything for them.
    """
    group = _get_group_or_404(session, group_uuid)
    in_sync = 0
    pending = 0
    skipped = 0
    for device in group.devices:
        if device.device_type != DeviceType.LUMESTRIO:
            skipped += 1
        elif device.config_version == device.synced_version:
            in_sync += 1
        else:
            pending += 1

    parts = [f"{in_sync} lumestrio device(s) in sync"]
    if pending:
        parts.append(f"{pending} pending")
    if skipped:
        parts.append(f"{skipped} relaystrio skipped (not yet supported)")
    return Message(message=", ".join(parts))


@router.delete("/", response_model=Message)
def delete_groups(session: SessionDep, payload: BulkDeleteRequest) -> Message:
    groups = crud.get_groups_by_uuids(session=session, uuids=payload.uuids)
    missing = set(payload.uuids) - {group.uuid for group in groups}
    if missing:
        raise HTTPException(
            status_code=404,
            detail=f"Group(s) not found: {', '.join(str(u) for u in sorted(missing))}",
        )
    in_use = [group for group in groups if group.devices]
    if in_use:
        raise HTTPException(
            status_code=409,
            detail="Group(s) still assigned to one or more devices: "
            + ", ".join(str(group.uuid) for group in in_use),
        )
    crud.delete_groups(session=session, db_groups=groups)
    return Message(message=f"{len(groups)} group(s) deleted successfully")
