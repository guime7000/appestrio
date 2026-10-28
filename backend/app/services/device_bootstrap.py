"""Item 9's devices-row bootstrap: on `backend` startup, if this Pi is
master (`Settings.IS_MASTER`), make sure it has its own `devices` row
flagged `is_master=True` -- the piece explicitly deferred from item 9's
first pass (`/whoami` itself never needed this row to exist). Matters
once something needs a real row for the master device (showing it in
the device list, letting an admin assign it audio/DMX capabilities or a
group, etc.) -- not for `/whoami`'s own frontend-gating use case, which
deliberately reads `Settings` directly instead.
"""

import logging

from sqlmodel import Session

from app import crud
from app.core.identity import resolve_own_device_identity
from app.models import Device

logger = logging.getLogger(__name__)


def bootstrap_own_device(session: Session) -> Device | None:
    identity = resolve_own_device_identity()
    if identity is None:
        logger.info(
            "master's own hostname doesn't match the <device_type><number> "
            "convention -- not a lumestrio endpoint, skipping devices-row bootstrap"
        )
        return None
    device_type, device_number = identity
    try:
        device = crud.ensure_own_master_device(
            session=session, device_type=device_type, device_number=device_number
        )
    except crud.MasterDeviceConflictError:
        logger.exception("devices-row bootstrap failed")
        return None
    logger.info("own device row ensured: device_id=%s", device.device_id)
    return device
