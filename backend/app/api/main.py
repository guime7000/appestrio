from fastapi import APIRouter

from app.api.routes import (
    agenda,
    calendars,
    devices,
    groups,
    ignition_presets,
    lora_settings,
    whoami,
)

api_router = APIRouter()
api_router.include_router(agenda.router)
api_router.include_router(calendars.router)
api_router.include_router(groups.router)
api_router.include_router(devices.router)
api_router.include_router(ignition_presets.router)
api_router.include_router(lora_settings.router)
api_router.include_router(whoami.router)
