import logging
import uuid

from fastapi import APIRouter, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from app import crud
from app.api.deps import SessionDep
from app.models import (
    ActivateRequest,
    Device,
    DeviceBulkDeleteRequest,
    DeviceCreate,
    DevicePublic,
    DevicesPublic,
    DeviceSyncConfigRequest,
    DeviceType,
    DeviceUpdate,
    FreeDeviceNumbers,
    Group,
    Message,
    PendingSyncPublic,
    address_for_device,
)
from app.services import lora_daemon_client
from app.services.activation import apply_active_state
from app.services.lora_daemon_client import LoraDaemonError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/devices", tags=["devices"])


def _get_device_or_404(session: SessionDep, device_id: str) -> Device:
    device = crud.get_device_by_device_id(session=session, device_id=device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return device


def _check_group_exists(session: SessionDep, group_id: uuid.UUID | None) -> None:
    if group_id is not None and not session.get(Group, group_id):
        raise HTTPException(status_code=404, detail="Group not found")


def _check_master_not_grouped(*, is_master: bool, group_id: uuid.UUID | None) -> None:
    """The master device is never part of a group -- guard requested
    2026-11-04, enforced here (not just hidden in the frontend form's
    "Groupe" select) so a direct API call can't bypass it either.
    """
    if is_master and group_id is not None:
        raise HTTPException(
            status_code=400, detail="The master device cannot be assigned to a group"
        )


def _check_master_active_unchanged(*, is_master: bool, active_changed: bool) -> None:
    """The master device has no on/off button anywhere in the app --
    guard requested 2026-11-04, enforced here so a direct `PATCH` can't
    bypass the frontend's own hidden/removed button either. Master is
    already never evaluated by the local agenda evaluator (confirmed
    2026-10-28 -- it's always on, owns no calendar of its own), so this
    doesn't change any real scheduling behavior, just closes off the
    one remaining way `active` could still be flipped for it.
    """
    if is_master and active_changed:
        raise HTTPException(
            status_code=400, detail="The master device's active state can't be toggled directly"
        )


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


@router.get("/pending-sync", response_model=PendingSyncPublic)
def get_pending_sync(session: SessionDep) -> PendingSyncPublic:
    devices = crud.get_devices_pending_sync(session=session)
    return PendingSyncPublic(count=len(devices), device_ids=[d.device_id for d in devices])


@router.post("/broadcast-activate", response_model=Message)
def broadcast_activate(session: SessionDep, payload: ActivateRequest) -> Message:
    """The Inauguration page's "Allumer"/"Eteindre" (frontend/src/views/
    InaugurationView.vue) -- replaced 2026-11-04's N individual
    per-device `PATCH /devices/{id}` calls (same pattern Groupes' "Tout
    éteindre/allumer" still uses) with this: one real **broadcast**
    ACTIVATE/DEACTIVATE LoRa frame, since the whole fleet is meant to
    turn on/off together here, not device-by-device.

    Local DB writes mirror what each individual PATCH already did
    (`crud.set_device_active` -- `active` is state, not config, no
    `config_version` bump, same rule `update_device`'s own PATCH path
    follows), just looped locally rather than one HTTP round trip per
    device. The LoRa side is the real change: a single
    `lora_daemon_client.send_activate(addresses=None)` call, which
    `lora-daemon`'s own `orchestration.send_activate` already encodes as
    one true broadcast-addressed frame (`messages.encode_activate`),
    not a loop -- best-effort, same posture as `_trigger_remote_activate`.

    The master device's own `active` column is deliberately left alone
    here too (2026-11-04's "no on/off button anywhere" guard) -- the
    real LoRa frame still reaches every device including master (a true
    broadcast can't selectively exclude one address at the radio level,
    and master receiving it is harmless), only this app's own local
    state for master is never toggled by it.
    """
    devices = [d for d in session.exec(select(Device)).all() if not d.is_master]
    for device in devices:
        crud.set_device_active(session=session, device=device, active=payload.active)

    try:
        lora_daemon_client.send_activate(payload.active, addresses=None)
    except LoraDaemonError:
        logger.warning(
            "couldn't reach lora-daemon to broadcast activate=%s", payload.active
        )

    return Message(
        message=f"broadcast activate={payload.active} applied to {len(devices)} device(s)"
    )


@router.get("/{device_id}", response_model=DevicePublic)
def get_device(session: SessionDep, device_id: str) -> DevicePublic:
    device = _get_device_or_404(session, device_id)
    return crud.device_to_public(device)


@router.post("/", response_model=DevicePublic, status_code=201)
def create_device(session: SessionDep, device_in: DeviceCreate) -> DevicePublic:
    _check_group_exists(session, device_in.group_id)
    _check_master_not_grouped(is_master=device_in.is_master, group_id=device_in.group_id)
    try:
        device = crud.create_device(session=session, device_create=device_in)
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail=_conflict_detail(exc))
    return crud.device_to_public(device)


def _trigger_remote_activate(device: Device, *, active: bool) -> None:
    # Best-effort: the DB write (the admin's actual intent) already
    # succeeded by the time this is called, and `active` is self-healing
    # anyway (the next PONG reconciles ground truth) -- so a `lora-daemon`
    # that's temporarily unreachable shouldn't fail the whole request.
    try:
        lora_daemon_client.send_activate(active, addresses=[address_for_device(device)])
    except LoraDaemonError:
        logger.warning(
            "couldn't reach lora-daemon to activate %s (active=%s)", device.device_id, active
        )


@router.patch("/{device_id}", response_model=DevicePublic)
def update_device(
    session: SessionDep, device_id: str, device_in: DeviceUpdate
) -> DevicePublic:
    device = _get_device_or_404(session, device_id)
    _check_group_exists(session, device_in.group_id)

    effective_is_master = (
        device_in.is_master if "is_master" in device_in.model_fields_set else device.is_master
    )
    effective_group_id = (
        device_in.group_id if "group_id" in device_in.model_fields_set else device.group_id
    )
    _check_master_not_grouped(is_master=effective_is_master, group_id=effective_group_id)

    active_changed = "active" in device_in.model_fields_set
    _check_master_active_unchanged(is_master=effective_is_master, active_changed=active_changed)

    try:
        device = crud.update_device(session=session, db_device=device, device_in=device_in)
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail=_conflict_detail(exc))

    # Real, immediate ACTIVATE over LoRa, on top of the DB write above
    # (which `update_device` already keeps "state, not config" --
    # doesn't bump `config_version` for this). Closes the gap flagged
    # 2026-10-28: clicking "Éteindre"/"Tout éteindre" updated this
    # column but never actually commanded the physical device.
    if active_changed:
        _trigger_remote_activate(device, active=device.active)

    return crud.device_to_public(device)


@router.post("/{device_id}/activate", response_model=Message)
def activate_device(session: SessionDep, device_id: str, payload: ActivateRequest) -> Message:
    """Called by this device's own `lora-daemon` when an ACTIVATE frame
    addressed to it arrives (item 8 step 3) -- not by the frontend.
    `lora-daemon` already reconciled its own local `devices.active` row
    directly (db.reconcile_device_active, same shared sqlite file); this
    route is purely the trigger for the physical side effect.
    """
    device = _get_device_or_404(session, device_id)
    apply_active_state(
        device_id=device.device_id,
        active=payload.active,
        handles_audio=device.handles_audio,
        handles_dmx=device.handles_dmx,
        audiofile=device.audiofile,
    )
    return Message(message=f"activation applied for {device_id}")


@router.post("/sync-config", response_model=Message)
def sync_config(session: SessionDep, payload: DeviceSyncConfigRequest) -> Message:
    """"Push configuration now" (the pending-sync banner's button): pushes
    each requested device's current desired config over LoRa and, once
    lora-daemon confirms delivery, marks it synced -- the write
    counterpart to the read-only `/pending-sync` count and to groups.py's
    "Test calendrier" check.

    Devices are pushed strictly one at a time, in sequence: lora-daemon's
    sync_device_config pauses/resumes its own scheduler for the duration
    of each push and has no guard against two concurrent pushes stepping
    on each other's pause/resume or colliding on the shared LoRa channel,
    so this route is the one place that enforces "never two pushes in
    flight at once" by construction. For a handful of pending devices
    this can genuinely take tens of seconds to a few minutes -- callers
    should show a busy state, not a tight timeout.
    """
    devices = crud.get_devices_by_device_ids(session=session, device_ids=payload.device_ids)
    missing = set(payload.device_ids) - {device.device_id for device in devices}
    if missing:
        raise HTTPException(
            status_code=404,
            detail=f"Device(s) not found: {', '.join(sorted(missing))}",
        )

    pending = [d for d in devices if d.config_version != d.synced_version]
    if not pending:
        return Message(message="Aucune configuration en attente pour les appareils sélectionnés.")

    succeeded = 0
    failed: list[str] = []
    for device in pending:
        try:
            pushed = lora_daemon_client.sync_device_config_and_wait(device.device_id)
        except LoraDaemonError:
            logger.warning("couldn't reach lora-daemon to push config for %s", device.device_id)
            failed.append(device.device_id)
            continue
        if not pushed:
            failed.append(device.device_id)
            continue

        if device.device_type == DeviceType.LUMESTRIO:
            # Real confirmation: ask the device itself for its own
            # applied config_version, same as "Test calendrier".
            try:
                results = lora_daemon_client.check_config_sync([device.device_id])
            except LoraDaemonError:
                results = {}
            confirmed = results.get("results", {}).get(device.device_id, False)
        else:
            # relaystrio has no device-confirmable "is this actually in
            # sync" signal at all -- no config_version field (see
            # groups.py's test_calendar), and lora-daemon's own
            # sync_device_config deliberately doesn't wait on a
            # missing-parts reply for this device_type either (2026-10-29
            # field feedback: don't gate relaystrio's sync status on any
            # device response). sync_device_config_and_wait already
            # returned True as soon as the chunks were sent, so there's
            # nothing further to confirm here.
            confirmed = True

        if confirmed:
            crud.mark_device_synced(session=session, device=device, version=device.config_version)
            succeeded += 1
        else:
            failed.append(device.device_id)

    parts = [f"{succeeded}/{len(pending)} appareil(s) mis à jour."]
    if failed:
        parts.append(f"Échec pour : {', '.join(sorted(failed))}.")
    return Message(message=" ".join(parts))


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
