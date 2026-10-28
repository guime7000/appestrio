from fastapi import APIRouter

from app.models import AgendaDisabledRequest, Message
from app.services import agenda_evaluator

router = APIRouter(prefix="/agenda", tags=["agenda"])


@router.post("/disabled", response_model=Message)
def set_agenda_disabled(payload: AgendaDisabledRequest) -> Message:
    """Called by this device's own `lora-daemon` on every DISABLE_AGENDA
    frame (and every broadcast ACTIVATE, which implicitly disables the
    agenda too -- see `EndpointResponder`). Kept purely in-memory
    (`agenda_evaluator`'s module-level flag), never persisted -- resets
    to enabled on every restart, matching legacy's own RAM-only
    `isAgendaDisabled` semantics.
    """
    agenda_evaluator.set_agenda_disabled(payload.disabled)
    return Message(message=f"agenda disabled={payload.disabled}")
