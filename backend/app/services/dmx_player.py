"""Generic start/stop of a loaded QLC+ show, over QLC+'s own WebSocket
API (`ws://<host>:9999/qlcplusWS`) -- settled 2026-11-03 after verifying
directly against a real running QLC+ 4.12.6 container (see
Docs/Claude_steps/...): `QLC+API|getFunctionsList` /
`QLC+API|getFunctionType|<id>` discover every Function's ID/type *after*
a project is loaded, and `QLC+API|setFunctionStatus|<id>|<0 or 1>` stops
or starts one by ID.

This never touches the .qxw project file itself (can't -- it may come
from an external partner appestrio has no business editing) and never
addresses a Virtual Console widget (would break on a project with an
empty VC, confirmed to be a real case here). Addressing Functions
discovered live, by ID, is the only part of QLC+'s control surface that
works regardless of what a given project's VC looks like.

**Convention**: only Functions of QLC+'s own `Show` type are started or
stopped. A `Show` is already the top-level timeline that sequences its
own `Scene`/`Chaser` building blocks, so "every `Show`-type Function in
the loaded project" is the most generic stand-in for "the light show(s)
to run" that doesn't require any per-project configuration. A project
with more than one `Show` function (confirmed to be a real case in the
sample file used to validate this) has all of them started/stopped
together -- picking "the one real show" among several is a project-
authoring problem, not something this module can resolve generically.

Uses the synchronous `websocket-client` package, not `websockets`
(asyncio) -- `apply_active_state` runs from plain synchronous call sites
(a sync FastAPI route, and `agenda_evaluator`'s blocking call from inside
its own already-running event loop), where `asyncio.run()` would raise.
"""

import logging

import websocket

from app.core.config import settings

logger = logging.getLogger(__name__)


class DmxPlayerError(Exception):
    pass


def _ws_url() -> str:
    return f"ws://{settings.QLCPLUS_HOST}:{settings.QLCPLUS_WS_PORT}/qlcplusWS"


def _connect() -> websocket.WebSocket:
    try:
        return websocket.create_connection(_ws_url(), timeout=settings.QLCPLUS_WS_TIMEOUT_S)
    except OSError as exc:
        raise DmxPlayerError(f"couldn't connect to QLC+ at {_ws_url()}: {exc}") from exc


def _list_show_function_ids(ws: websocket.WebSocket) -> list[int]:
    ws.send("QLC+API|getFunctionsList")
    reply = ws.recv()
    parts = str(reply).split("|")
    # Reply shape: QLC+API|getFunctionsList|<id>|<name>|<id>|<name>|...
    if len(parts) < 3 or parts[0] != "QLC+API" or parts[1] != "getFunctionsList":
        return []
    function_ids = [int(fid) for fid in parts[2::2]]

    show_ids = []
    for function_id in function_ids:
        ws.send(f"QLC+API|getFunctionType|{function_id}")
        type_reply = str(ws.recv())
        if type_reply.split("|")[-1] == "Show":
            show_ids.append(function_id)
    return show_ids


def _set_shows_status(active: bool) -> None:
    ws = _connect()
    try:
        try:
            show_ids = _list_show_function_ids(ws)
        except (OSError, websocket.WebSocketException) as exc:
            raise DmxPlayerError(f"couldn't talk to QLC+ at {_ws_url()}: {exc}") from exc
        if not show_ids:
            logger.warning("qlc+: no Show-type function found in the currently loaded project")
            return
        status = 1 if active else 0
        for function_id in show_ids:
            ws.send(f"QLC+API|setFunctionStatus|{function_id}|{status}")
    finally:
        ws.close()


def start_show() -> None:
    _set_shows_status(True)


def stop_show() -> None:
    _set_shows_status(False)
