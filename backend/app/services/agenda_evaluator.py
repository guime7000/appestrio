"""Item 7: the local on/off scheduling loop every `lumestrio` needs --
"given my resolved calendar and the current time, should I be on right
now?" -- ported from `relaystrio`'s own firmware behavior
(`SchedulerAPI.h`'s periodic `updateStateFromAgenda`), see
Docs/To_Be_Done.md item 7 and Legacy/Audits/relaystrio.md §2.2 for the
semantics this follows.

**Which device is "me"?** No hostname parsing needed in `backend` (that
stays `lora-daemon`-only, item 8 step 1) -- a slave's local DB always
holds exactly one `devices` row (item 8's `apply_pushed_config` never
creates more than one), so "the only row" IS this device. Master's own
multi-device DB is **not** evaluated by this loop at all: master is
always on and owns no calendar of its own (confirmed 2026-10-28) --
`resolve_own_device` simply returns `None` whenever more than one row
exists, which is exactly the right behavior, not a special case.

**`DISABLE_AGENDA`**: kept purely in-memory here (module-level), reset to
`False` on every process restart -- faithfully matching legacy
(`RootAPI::isAgendaDisabled` lives in RAM only, never written to SPIFFS;
a reboot always resumes agenda-driven behavior). Set via the reverse
HTTP route `lora_daemon`'s `EndpointResponder` calls into
(`POST /agenda/disabled`) on every `DISABLE_AGENDA` frame, and on every
**broadcast** `ACTIVATE` too (`Activate.is_multi()`) -- matching
`LoraApp::onRxFlag`'s own "a broadcast activate additionally disables the
agenda" rule (relaystrio.md §2.2) so a mass remote override isn't
immediately fought by the next tick. A **targeted** (single-device)
`ACTIVATE` deliberately does *not* disable the agenda -- same faithful
port -- so it's momentary and can be overwritten by this evaluator's very
next tick, exactly like legacy.
"""

import asyncio
import contextlib
import logging
from datetime import datetime

from sqlmodel import Session, func, select

from app import crud
from app.core.db import engine
from app.models import Device
from app.models.ignition_presets import parse_date, parse_time
from app.services.activation import apply_active_state

logger = logging.getLogger(__name__)

DEFAULT_INTERVAL_S = 30.0

_agenda_disabled = False


def set_agenda_disabled(disabled: bool) -> None:
    global _agenda_disabled
    _agenda_disabled = disabled


def is_agenda_disabled() -> bool:
    return _agenda_disabled


def resolve_own_device(session: Session) -> Device | None:
    """Exactly one row in this local DB -> that's us. Zero (not
    provisioned yet) or more than one (master's own multi-device DB, or a
    slave mid-provisioning with a stale extra row) -> nothing for this
    evaluator to do.
    """
    count = session.exec(select(func.count()).select_from(Device)).one()
    if count != 1:
        return None
    return session.exec(select(Device)).one()


def compute_desired_active(device: Device, *, now: datetime) -> bool:
    if device.group is None or device.group.calendar is None:
        return False
    calendar = device.group.calendar
    if now.isoweekday() not in calendar.weekdays:
        return False
    today = now.date()
    now_time = now.time()
    for preset in calendar.ignition_presets:
        if (
            parse_date(preset.start_date).date() <= today <= parse_date(preset.stop_date).date()
            and parse_time(preset.start_time).time()
            <= now_time
            <= parse_time(preset.stop_time).time()
        ):
            return True
    return False


def evaluate_once(session: Session, *, now: datetime | None = None) -> None:
    if is_agenda_disabled():
        return
    device = resolve_own_device(session)
    if device is None:
        return
    desired_active = compute_desired_active(device, now=now or datetime.now())
    if desired_active == device.active:
        return
    crud.set_device_active(session=session, device=device, active=desired_active)
    apply_active_state(
        device_id=device.device_id,
        active=desired_active,
        handles_audio=device.handles_audio,
        handles_dmx=device.handles_dmx,
        audiofile=device.audiofile,
    )


async def run_forever(
    *, interval_s: float = DEFAULT_INTERVAL_S, stop: asyncio.Event | None = None
) -> None:
    if stop is None:
        stop = asyncio.Event()
    while not stop.is_set():
        try:
            with Session(engine) as session:
                evaluate_once(session)
        except Exception:
            logger.exception("agenda evaluator tick failed")
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), timeout=interval_s)
