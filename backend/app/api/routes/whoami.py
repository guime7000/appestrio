from fastapi import APIRouter

from app.core.config import settings
from app.models import WhoAmI

router = APIRouter(tags=["whoami"])


@router.get("/whoami", response_model=WhoAmI)
def whoami() -> WhoAmI:
    """Reads `IS_MASTER` directly from Settings -- no DB lookup -- so the
    frontend can gate configuration pages (hide them unless the device
    you're connected to via WiFi is master) without depending on a
    `devices` row that might not exist yet on a device that hasn't
    received its first config push (Docs/To_Be_Done.md item 9).
    """
    return WhoAmI(is_master=settings.IS_MASTER)
