"""`apply_active_state` -- the one function that actually turns a
`lumestrio` on/off physically (OSC to QLC+ for DMX-capable devices, `mpv`
audio playback -- design settled 2026-10-24, see Docs/To_Be_Done.md
item 7). Shared by two callers that both just learned "this device
should now be active=X": item 8's `ACTIVATE` handling (via
`/devices/{device_id}/activate`) and item 7's local agenda evaluator.

**Audio wired to real `mpv` playback 2026-11-01**, via
`app/services/audio_player.py` (built for the Audio config/testing page,
2026-10-29/30) -- this is exactly the "one place the real
`apply_active_state` implementation should read from" that module's own
docstring already called out. `audiofile` (this device's
master-configured show file, from the `devices` table) is written into
`audio_player`'s own persisted state on every activation, so it stays
the single source of truth for "which file" while `audio_player`'s own
volume/loop calibration (set via the Audio page, no master-side
equivalent) carries over unchanged -- the same self-healing pattern
`active` itself already follows elsewhere in this codebase (every real
signal overwrites local state, never just assumed). A device with no
`audiofile` configured, or a file that hasn't actually been uploaded to
this Pi yet (LoRa can't transmit audio bytes, only the filename
reference), fails loud in the logs rather than crashing the caller --
same best-effort posture as `_trigger_remote_activate`.

**Relay (the audio amp's power) wired the same day**, via
`app/services/relay.py` -- ported from legacy's `modules/Relay.ts`
(GPIO pin 25, toggled unconditionally alongside play/stop, not driven
by player state or acknowledged in any way -- see that module's own
docstring). Same call order as legacy's `sendStartOrStopMessage`: audio
first, then the relay, in both directions.

**DMX wired 2026-11-03**, via `app/services/dmx_player.py` -- QLC+'s own
WebSocket API, addressing Functions by ID discovered live rather than
anything in the project file itself (so it works against any partner-
supplied .qxw, never edited, see that module's own docstring for the
full design). Best-effort posture, same as audio: a `DmxPlayerError`
(QLC+ unreachable, e.g. `compose.dmx.yml` not included on this device)
is logged and swallowed, never raised to the caller.
"""

import logging

from app.services import audio_player, dmx_player, relay
from app.services.audio_player import AudioPlayerError
from app.services.dmx_player import DmxPlayerError

logger = logging.getLogger(__name__)


def _start_audio_playback(device_id: str, audiofile: str | None) -> None:
    if audiofile:
        state = audio_player.load_state()
        audio_player.save_state(
            volume=state["volume"],
            audiofile=audiofile,
            test_audiofile=state["test_audiofile"],
            loop=state["loop"],
        )
    try:
        audio_player.play()
    except AudioPlayerError as exc:
        logger.warning("%s: couldn't start audio playback: %s", device_id, exc)
    relay.activate(True)


def _start_dmx_show(device_id: str) -> None:
    try:
        dmx_player.start_show()
    except DmxPlayerError as exc:
        logger.warning("%s: couldn't start QLC+ show: %s", device_id, exc)


def _stop_dmx_show(device_id: str) -> None:
    try:
        dmx_player.stop_show()
    except DmxPlayerError as exc:
        logger.warning("%s: couldn't stop QLC+ show: %s", device_id, exc)


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
            _start_dmx_show(device_id)
        if handles_audio:
            _start_audio_playback(device_id, audiofile)
        if not handles_dmx and not handles_audio:
            logger.info("[placeholder] %s: activated, but handles neither audio nor DMX", device_id)
    else:
        if handles_dmx:
            _stop_dmx_show(device_id)
        if handles_audio:
            audio_player.stop()
            relay.activate(False)
        if not handles_dmx and not handles_audio:
            logger.info(
                "[placeholder] %s: deactivated, but handles neither audio nor DMX", device_id
            )
