"""Sets this device's system clock and writes it through to the
physical RTC module plugged into the GPIO pins -- both `relaystrio` and
`lumestrio` have one (confirmed 2026-10-28). This is the receive side of
`SYNC`, item 8's last gap (Docs/Lora_Daemon_To_Be_Done.md §5):
master already broadcasts `SYNC` on a schedule
(`orchestration.run_clock_sync_forever`), nothing on the receiving
`lumestrio` end acted on one until now.

Two separate operations, in order:
1. Set the system clock (`date -s`) -- what every other process on this
   device actually reads moment to moment.
2. Write it through to the hardware RTC (`hwclock --systohc`) -- so the
   correct time survives a power cycle without needing a fresh `SYNC`
   immediately on the next boot, which matters for a field deployment
   with intermittent power and no internet/NTP access (the whole reason
   this LoRa-based time-sync exists instead of just using NTP).

Both need `CAP_SYS_TIME` (the kernel's `settimeofday` and the RTC
driver's `RTC_SET_TIME` ioctl both gate on it); the second also needs
the RTC device node passed through (`/dev/rtc0` in `compose.yml`).
Logs and swallows any failure instead of raising -- a missing
capability/device grant (local dev, a misconfigured deploy, a device
whose RTC isn't actually wired up yet) must not crash the whole
daemon's dispatch loop over one `SYNC` frame, same non-fatal spirit as
every other cross-process/cross-privilege boundary in this codebase.
Treated as local, fast, synchronous calls (milliseconds) -- no need for
the async fire-and-forget scheduling the HTTP reverse-channel calls
elsewhere in `endpoint.py` need, since there's no network round-trip
here.
"""

import logging
import subprocess
from datetime import datetime

logger = logging.getLogger(__name__)

_DATE_COMMAND_FORMAT = "%Y-%m-%d %H:%M:%S"


def set_system_and_hardware_clock(when: datetime) -> None:
    formatted = when.strftime(_DATE_COMMAND_FORMAT)
    try:
        subprocess.run(["date", "-s", formatted], check=True, capture_output=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        logger.warning("couldn't set system clock to %s: %s", formatted, exc)
        return
    logger.info("system clock set to %s", formatted)
    try:
        subprocess.run(
            ["hwclock", "--systohc", "--localtime"], check=True, capture_output=True
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        logger.warning("system clock set, but couldn't write through to the RTC module: %s", exc)
        return
    logger.info("RTC module updated from system clock")
