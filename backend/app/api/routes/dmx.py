"""Gates the frontend's "QLC+" nav link for `handles_dmx` devices --
QLC+ itself (`qlcplus/`, a separate container, only started via the
opt-in `compose.dmx.yml` overlay on devices that actually have a DMX
interface wired up) is reached directly by the browser on its own
port (9999), the same way lora-daemon's own hardware test console is
reached directly on 8765 -- nothing here proxies it or embeds it.
"""

from fastapi import APIRouter

from app.api.deps import SessionDep
from app.models import DmxStatusPublic
from app.services.device_identity import resolve_this_device

router = APIRouter(prefix="/dmx", tags=["dmx"])


@router.get("/status", response_model=DmxStatusPublic)
def get_status(session: SessionDep) -> DmxStatusPublic:
    device = resolve_this_device(session)
    return DmxStatusPublic(handles_dmx=bool(device and device.handles_dmx))
