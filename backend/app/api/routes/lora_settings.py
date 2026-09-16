from fastapi import APIRouter

from app import crud
from app.api.deps import SessionDep
from app.models import LoraSettings, LoraSettingsPublic, LoraSettingsUpdate

router = APIRouter(prefix="/lora-settings", tags=["lora-settings"])


@router.get("/", response_model=LoraSettingsPublic)
def get_lora_settings(session: SessionDep) -> LoraSettings:
    return crud.get_lora_settings(session=session)


@router.patch("/", response_model=LoraSettingsPublic)
def update_lora_settings(
    session: SessionDep, settings_in: LoraSettingsUpdate
) -> LoraSettings:
    return crud.update_lora_settings(session=session, settings_in=settings_in)
