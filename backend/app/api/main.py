from fastapi import APIRouter

from app.api.routes import calendars, devices

api_router = APIRouter()
api_router.include_router(calendars.router)
api_router.include_router(devices.router)
