from fastapi import APIRouter

from app.api.routes import calendars, devices, groups, ignition_presets

api_router = APIRouter()
api_router.include_router(calendars.router)
api_router.include_router(groups.router)
api_router.include_router(devices.router)
api_router.include_router(ignition_presets.router)
