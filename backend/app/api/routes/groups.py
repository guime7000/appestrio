import logging
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
from app.services import lora_daemon_client
from app.services.lora_daemon_client import LoraDaemonError

logger = logging.getLogger(__name__)

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
    """"Test calendrier" (GroupsView.vue): a real, on-demand verification
    that every device in the group actually has the right calendar
    applied, not a config push.

    For `lumestrio`: asks each device directly, live, over LoRa
    (`lora_daemon_client.check_config_sync` -> `orchestration
    .check_lumestrio_config_sync`) -- a real `WITH_CONFIG_VERSION` round
    trip, not an inference from "no missing chunks were reported" (see
    that function's own docstring for why that distinction matters, and
    why checking several devices at once is paced to avoid flooding the
    shared LoRa channel). A device the call doesn't hear back from
    within its response window -- or every device, if `lora-daemon`
    itself is unreachable -- is reported as pending, never silently
    assumed in sync from stale local data.

    For `relaystrio`: no live check is possible at all -- the frozen
    firmware has no way to report its own applied `config_version` back
    (no field, no concept). The best that can ever be said is the same
    optimistic "master believes it pushed successfully"
    `config_version == synced_version` comparison `sync_device_config`
    already relies on -- reported separately, and labeled "presumed",
    never conflated with a `lumestrio`'s actual confirmation.
    """
    group = _get_group_or_404(session, group_uuid)
    lumestrio_devices = [d for d in group.devices if d.device_type == DeviceType.LUMESTRIO]
    relaystrio_devices = [d for d in group.devices if d.device_type == DeviceType.RELAYSTRIO]

    live_results: dict[str, bool] = {}
    if lumestrio_devices:
        try:
            response = lora_daemon_client.check_config_sync(
                [device.device_id for device in lumestrio_devices]
            )
            live_results = response["results"]
        except LoraDaemonError:
            logger.warning("couldn't reach lora-daemon for a live config-sync check")

    parts = []
    if lumestrio_devices:
        lumestrio_in_sync = sum(
            1 for device in lumestrio_devices if live_results.get(device.device_id) is True
        )
        parts.append(
            f"{lumestrio_in_sync}/{len(lumestrio_devices)} lumestrio device(s) confirmed in sync"
        )
    if relaystrio_devices:
        relaystrio_in_sync = sum(
            1
            for device in relaystrio_devices
            if device.config_version == device.synced_version
        )
        parts.append(
            f"{relaystrio_in_sync}/{len(relaystrio_devices)} relaystrio device(s) presumed in "
            "sync (no confirmation possible)"
        )
    if not parts:
        return Message(message="no devices in this group")
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
