"""Gates the frontend's "QLC+" nav link for `handles_dmx` devices --
QLC+ itself (`qlcplus/`, a separate container, run unconditionally by
every lumestrio since 2026-11-03's generic-image decision) is reached
directly by the browser on its own port (9999), the same way
lora-daemon's own hardware test console is reached directly on 8765 --
nothing here proxies it or embeds it.

Also the Upload page's "Projet QLC+" field (`POST /dmx/upload`) --
accepts the show project (`.qxw`) and fixture library (`.qxf`) files
together in one multi-file request, sorted by extension and handed to
`app/services/qlc_files.py` for storage (see that module's own
docstring for the full design: why a project upload replaces any
existing one, why fixtures are additive, and why only the project gets
a live-reload push into the running `qlcplus` container).
"""

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile
from sqlmodel import Session

from app.api.deps import SessionDep
from app.core.config import settings
from app.models import DmxStatusPublic, Message
from app.services import qlc_files
from app.services.device_identity import resolve_this_device

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dmx", tags=["dmx"])

ALLOWED_EXTENSIONS = qlc_files.ALLOWED_PROJECT_EXTENSIONS | qlc_files.ALLOWED_FIXTURE_EXTENSIONS


def _require_dmx_device(session: Session) -> None:
    """Same two-case gate as the Audio page's `_require_audio_device`:
    404 for a not-yet-provisioned device, 400 for one that genuinely
    doesn't handle DMX.
    """
    device = resolve_this_device(session)
    if device is None:
        raise HTTPException(status_code=404, detail="This device isn't provisioned yet")
    if not device.handles_dmx:
        raise HTTPException(status_code=400, detail="This device doesn't handle DMX")


@router.get("/status", response_model=DmxStatusPublic)
def get_status(session: SessionDep) -> DmxStatusPublic:
    device = resolve_this_device(session)
    return DmxStatusPublic(handles_dmx=bool(device and device.handles_dmx))


@router.post("/upload", response_model=Message)
async def upload(session: SessionDep, files: list[UploadFile]) -> Message:
    _require_dmx_device(session)
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    saved_project = 0
    saved_fixtures = 0
    for file in files:
        filename = Path(file.filename or "").name
        extension = Path(filename).suffix.lower()
        if not filename or extension not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400, detail=f"Unsupported file type: {filename or '(no filename)'}"
            )
        contents = await file.read()
        if len(contents) > settings.QLC_MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail=f"File too large: {filename}")

        if extension in qlc_files.ALLOWED_PROJECT_EXTENSIONS:
            qlc_files.save_project(filename, contents)
            saved_project += 1
        else:
            qlc_files.save_fixture(filename, contents)
            saved_fixtures += 1

    return Message(
        message=f"saved {saved_project} project file(s), {saved_fixtures} fixture file(s)"
    )
