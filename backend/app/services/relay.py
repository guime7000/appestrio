"""GPIO relay control for the amp that powers a `handles_audio`
device's speaker -- ported from legacy's `modules/Relay.ts` (the
`pigpio` npm package, GPIO pin 25). Uses `gpiozero` instead of a
`pigpio`/`pigpiod` client: no separate daemon to run, talks to
`/dev/gpiomem` (or the newer gpiochip character device) directly.

Legacy toggles this unconditionally alongside starting/stopping audio
playback, from the same boolean, in `endpointServer.ts`'s
`sendStartOrStopMessage` -- not driven by player state or acknowledged
in any way. `app/services/activation.py` follows the same contract:
call `activate(True)`/`activate(False)` right alongside
`audio_player.play()`/`stop()`, never waiting on either.

`_make_device` is the one seam tests replace -- no real GPIO hardware
needed to exercise this module's own logic. Initialization failures
(no GPIO hardware at all, e.g. this running off a Pi) are logged and
treated as "nothing to do," the same best-effort posture every other
real-hardware integration in this codebase follows (lora-daemon
unreachable, mpv failing to start, etc).
"""

import logging
from typing import Protocol

from app.core.config import settings

logger = logging.getLogger(__name__)


class _Device(Protocol):
    def on(self) -> None: ...
    def off(self) -> None: ...
    def close(self) -> None: ...


_device: _Device | None = None
_device_pin: int | None = None


def _make_device(pin: int) -> _Device:  # pragma: no cover -- real GPIO, not unit-tested
    from gpiozero import OutputDevice

    return OutputDevice(pin)


def _get_device() -> _Device | None:
    global _device, _device_pin
    pin = settings.AUDIO_RELAY_GPIO_PIN
    if _device is not None and _device_pin == pin:
        return _device
    if _device is not None:
        _device.close()
        _device = None

    try:
        _device = _make_device(pin)
    except Exception:
        # Broad on purpose: gpiozero's own failure modes for "no GPIO
        # hardware/backend available" vary by platform (BadPinFactory,
        # GPIOZeroError, a missing native backend module, ...) -- all of
        # them mean the same thing here: there's no relay to drive.
        logger.exception("relay: couldn't initialize GPIO pin %s", pin)
        return None
    _device_pin = pin
    return _device


def activate(active: bool) -> None:
    device = _get_device()
    if device is None:
        return
    if active:
        device.on()
    else:
        device.off()
