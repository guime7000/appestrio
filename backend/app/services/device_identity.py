"""Which `devices` row IS this physical hardware -- a slave's local DB
only ever holds its own single row (`agenda_evaluator.resolve_own_device`'s
case), but master's holds every device's row too, since it configures
the whole network from here; master is still itself exactly one
physical Pi, identified among its own multi-row DB the same way item
9's bootstrap flags it: `is_master=True` (`crud.get_master_device`).

Deliberately NOT folded into `agenda_evaluator.resolve_own_device`
itself: master is confirmed to never run its own agenda loop
(2026-10-28, see that module's docstring), and widening that resolver
would silently reopen that decision. This one is only for things that
genuinely need "which hardware am I" regardless of role -- the Audio
and QLC+/DMX pages, so far -- master can have `handles_audio`/
`handles_dmx` set on its own row too (it's usually also a lumestrio
physically), and should be able to use either from its own dashboard.
"""

from sqlmodel import Session

from app import crud
from app.models import Device
from app.services.agenda_evaluator import resolve_own_device


def resolve_this_device(session: Session) -> Device | None:
    device = resolve_own_device(session)
    if device is not None:
        return device
    return crud.get_master_device(session=session)
