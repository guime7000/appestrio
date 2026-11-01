"""The Audio page: a local, per-device config/testing tool for
`handles_audio` devices -- upload an audio file, play/stop it, and tune
its volume, with the volume (and which file) persisted to disk so the
next playback (manual or, eventually, scheduled) picks up where you left
off. Reached by a user WiFi-connected directly to this specific
device's own webapp, same as every other page in this frontend -- not
routed through master or LoRa at all.

Explicitly a testing tool, not part of the live show: intended for use
while this device has been manually turned off (decided 2026-10-29),
so there's no attempt here to coordinate with `agenda_evaluator`'s
autonomous on/off scheduling -- see `app/services/audio_player.py`'s
own docstring for why this also deliberately never touches the
`devices` table's `audiofile` column.
"""

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile
from sqlmodel import Session

from app import crud
from app.api.deps import SessionDep
from app.core.config import settings
from app.models import AudioLoopRequest, AudioStatusPublic, AudioVolumeRequest, Device
from app.services import audio_player
from app.services.agenda_evaluator import resolve_own_device
from app.services.audio_player import AudioPlayerError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/audio", tags=["audio"])

ALLOWED_EXTENSIONS = {".mp3", ".wav", ".ogg", ".flac", ".m4a"}


def _resolve_this_device(session: Session) -> Device | None:
    """Which `devices` row IS this physical hardware -- a slave's local
    DB only ever holds its own single row (`resolve_own_device`'s case),
    but master's holds every device's row too, since it configures the
    whole network from here; master is still itself exactly one
    physical Pi, identified among its own multi-row DB the same way
    item 9's bootstrap flags it: `is_master=True`
    (`crud.get_master_device`). Deliberately NOT folded into
    `agenda_evaluator.resolve_own_device` itself: master is confirmed to
    never run its own agenda loop (2026-10-28, see that module's
    docstring), and widening that resolver would silently reopen that
    decision. This one is only for things that genuinely need "which
    hardware am I" regardless of role, like this page -- master can
    have `handles_audio` set on its own row too (it's usually also a
    lumestrio physically), and should be able to test it from its own
    dashboard.
    """
    device = resolve_own_device(session)
    if device is not None:
        return device
    return crud.get_master_device(session=session)


def _status() -> AudioStatusPublic:
    state = audio_player.load_state()
    return AudioStatusPublic(
        handles_audio=True,
        audiofile=state["audiofile"],
        test_audiofile=state["test_audiofile"],
        volume=state["volume"],
        loop=state["loop"],
        playing=audio_player.is_playing(),
    )


def _require_audio_device(session: Session) -> None:
    """404s for a not-yet-provisioned device, 400 for one that genuinely
    doesn't handle audio -- distinct cases so the frontend can tell "this
    device hasn't received its config yet" from "this device was never
    meant to have an Audio page" (same `handles_audio` gate the nav link
    itself uses `/audio/status` for).
    """
    device = _resolve_this_device(session)
    if device is None:
        raise HTTPException(status_code=404, detail="This device isn't provisioned yet")
    if not device.handles_audio:
        raise HTTPException(status_code=400, detail="This device doesn't handle audio")


@router.get("/status", response_model=AudioStatusPublic)
def get_status(session: SessionDep) -> AudioStatusPublic:
    device = _resolve_this_device(session)
    if device is None or not device.handles_audio:
        state = audio_player.load_state()
        return AudioStatusPublic(
            handles_audio=False,
            audiofile=None,
            test_audiofile=None,
            volume=state["volume"],
            loop=state["loop"],
            playing=False,
        )
    return _status()


@router.post("/play", response_model=AudioStatusPublic)
def play(session: SessionDep) -> AudioStatusPublic:
    _require_audio_device(session)
    try:
        audio_player.play()
    except AudioPlayerError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _status()


@router.post("/test", response_model=AudioStatusPublic)
def play_test(session: SessionDep) -> AudioStatusPublic:
    """The "Son test" button: plays the separate calibration sample
    uploaded via `/audio/upload-test`, independent of the main
    `audiofile` -- see `audio_player.play_test`'s own docstring.
    """
    _require_audio_device(session)
    try:
        audio_player.play_test()
    except AudioPlayerError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _status()


@router.post("/stop", response_model=AudioStatusPublic)
def stop(session: SessionDep) -> AudioStatusPublic:
    _require_audio_device(session)
    audio_player.stop()
    return _status()


@router.post("/volume", response_model=AudioStatusPublic)
def set_volume(session: SessionDep, payload: AudioVolumeRequest) -> AudioStatusPublic:
    _require_audio_device(session)
    audio_player.set_volume(payload.volume)
    return _status()


@router.post("/loop", response_model=AudioStatusPublic)
def set_loop(session: SessionDep, payload: AudioLoopRequest) -> AudioStatusPublic:
    """Shared by both playback slots -- there's only ever one mpv
    process, so this toggles looping for whichever file (main or test)
    is currently playing, and for whichever plays next.
    """
    _require_audio_device(session)
    audio_player.set_loop(payload.enabled)
    return _status()


def _save_uploaded_audio_file(contents: bytes, filename: str, *, subdir: str | None = None) -> str:
    """Writes `contents` under `AUDIO_DIR` (optionally a subdirectory,
    so the main and test-sound upload slots can never collide on disk
    just because someone picked the same filename for both) and returns
    the path to persist in `audio_player`'s state, relative to
    `AUDIO_DIR`.
    """
    audio_dir = Path(settings.AUDIO_DIR)
    target_dir = audio_dir / subdir if subdir else audio_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / filename).write_bytes(contents)
    return f"{subdir}/{filename}" if subdir else filename


async def _read_validated_upload(file: UploadFile) -> tuple[str, bytes]:
    filename = Path(file.filename or "").name
    extension = Path(filename).suffix.lower()
    if not filename or extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Unsupported audio file type")

    contents = await file.read()
    if len(contents) > settings.AUDIO_MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large")
    return filename, contents


@router.post("/upload", response_model=AudioStatusPublic)
async def upload(session: SessionDep, file: UploadFile) -> AudioStatusPublic:
    _require_audio_device(session)
    filename, contents = await _read_validated_upload(file)
    stored_path = _save_uploaded_audio_file(contents, filename)

    state = audio_player.load_state()
    audio_player.save_state(
        volume=state["volume"],
        audiofile=stored_path,
        test_audiofile=state["test_audiofile"],
        loop=state["loop"],
    )
    return _status()


@router.post("/upload-test", response_model=AudioStatusPublic)
async def upload_test(session: SessionDep, file: UploadFile) -> AudioStatusPublic:
    _require_audio_device(session)
    filename, contents = await _read_validated_upload(file)
    stored_path = _save_uploaded_audio_file(contents, filename, subdir="test")

    state = audio_player.load_state()
    audio_player.save_state(
        volume=state["volume"],
        audiofile=state["audiofile"],
        test_audiofile=stored_path,
        loop=state["loop"],
    )
    return _status()
