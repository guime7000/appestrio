from fastapi import APIRouter, HTTPException

from app import crud
from app.api.deps import SessionDep
from app.models import LoraSettings, LoraSettingsPublic, LoraSettingsUpdate, Message
from app.services import lora_daemon_client
from app.services.lora_daemon_client import LoraDaemonError

router = APIRouter(prefix="/lora-settings", tags=["lora-settings"])


@router.get("/", response_model=LoraSettingsPublic)
def get_lora_settings(session: SessionDep) -> LoraSettings:
    return crud.get_lora_settings(session=session)


@router.patch("/", response_model=LoraSettingsPublic)
def update_lora_settings(
    session: SessionDep, settings_in: LoraSettingsUpdate
) -> LoraSettings:
    return crud.update_lora_settings(session=session, settings_in=settings_in)


@router.post("/sync-now", response_model=Message)
def sync_clocks_now() -> Message:
    """Triggers an immediate SYNC broadcast via lora-daemon's control API,
    instead of only ever waiting out the rest of `clock_interval_s` --
    what "Synchroniser les horloges" calls (HorlogesView.vue).
    """
    try:
        lora_daemon_client.trigger_clock_sync()
    except LoraDaemonError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return Message(message="Clock sync sent")
