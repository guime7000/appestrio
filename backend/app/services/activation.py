"""`apply_active_state` -- the one function that would actually turn a
`lumestrio` on/off physically (OSC to QLC+ for DMX-capable devices, `mpv`
audio playback, a relay powering the audio amp -- design settled
2026-10-24, see Docs/To_Be_Done.md item 7). Shared by two callers that
both just learned "this device should now be active=X": item 8's
`ACTIVATE` handling (via the `/devices/{device_id}/activate` route below)
and item 7's local agenda evaluator (not built yet).

Deliberately a logging placeholder for now -- the real OSC/mpv/relay
infrastructure doesn't exist yet, and wiring this to real hardware is
explicitly the last piece of this project to get built. Every other
caller (the route, the future evaluator) should depend on this function's
signature, not on it actually doing anything yet.
"""

import logging

logger = logging.getLogger(__name__)


def apply_active_state(
    *,
    device_id: str,
    active: bool,
    handles_audio: bool,
    handles_dmx: bool,
    audiofile: str | None = None,
) -> None:
    if active:
        if handles_dmx:
            logger.info("[placeholder] %s: would send OSC to QLC+ to start DMX show", device_id)
        if handles_audio:
            logger.info(
                "[placeholder] %s: would start playback of %r via mpv and power the amp relay",
                device_id,
                audiofile,
            )
        if not handles_dmx and not handles_audio:
            logger.info("[placeholder] %s: activated, but handles neither audio nor DMX", device_id)
    else:
        logger.info("[placeholder] %s: would stop playback/DMX and power down the amp relay", device_id)
