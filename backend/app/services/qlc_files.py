"""Upload storage for the QLC+ show project (.qxw) and fixture library
(.qxf) -- the Upload page's combined "Projet QLC+" field
(`app/api/routes/dmx.py`'s `POST /dmx/upload`). Writes into the same
host-mounted folder `qlcplus/qlcplus.sh`'s own entrypoint scans at
startup for its one project file (directory-search autoload,
2026-11-04, see Docs/Claude_steps/
2026-11-04_qlc_autoload_and_stale_volume_fix.md) -- an uploaded project
survives a `qlcplus` container restart with zero extra wiring, same
directory, same convention.

A `.qxw` upload **replaces** any existing project file(s) in this
folder -- the autoloader refuses to guess when more than one is
present, so this module enforces "exactly one" on every project
upload rather than letting them accumulate. `.qxf` fixture uploads are
additive (QLC+'s fixture library is meant to hold many).

Also best-effort pushes a newly uploaded project straight into the
*already-running* `qlcplus` container's own `/loadProject` HTTP
endpoint -- the exact same mechanism `qlcplus.sh`'s entrypoint itself
uses at startup, confirmed working directly against a real container --
so a project update takes effect immediately, not just on the
container's next restart. Fixture uploads get no equivalent live push:
QLC+ only scans its fixture search path at its own process startup, and
no live-rescan API was found in the WebSocket protocol explored for
`app/services/dmx_player.py` -- a newly uploaded fixture needs a
`qlcplus` container restart to actually be recognized; saving it to
disk (so it's there on that next restart) is all this module attempts.
"""

import logging
from pathlib import Path

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

ALLOWED_PROJECT_EXTENSIONS = {".qxw"}
ALLOWED_FIXTURE_EXTENSIONS = {".qxf"}


def project_dir() -> Path:
    return Path(settings.QLC_PROJECT_DIR)


def fixtures_dir() -> Path:
    return project_dir() / "fixtures"


def save_project(filename: str, contents: bytes) -> Path:
    directory = project_dir()
    directory.mkdir(parents=True, exist_ok=True)
    for existing in directory.glob("*.qxw"):
        existing.unlink()
    path = directory / filename
    path.write_bytes(contents)
    _push_live_reload(path)
    return path


def save_fixture(filename: str, contents: bytes) -> Path:
    directory = fixtures_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / filename
    path.write_bytes(contents)
    return path


def _push_live_reload(path: Path) -> None:
    url = f"http://{settings.QLCPLUS_HOST}:{settings.QLCPLUS_WS_PORT}/loadProject"
    try:
        with (
            httpx.Client(timeout=settings.QLCPLUS_WS_TIMEOUT_S) as client,
            path.open("rb") as fh,
        ):
            client.post(url, files={"qlcprj": (path.name, fh)})
    except (httpx.HTTPError, OSError) as exc:
        logger.warning("qlc_files: couldn't live-reload the running qlcplus instance: %s", exc)
