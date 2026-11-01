"""Local mpv playback control for the Audio page -- a manual, per-device
config/testing tool for `handles_audio` devices, used while this device
is deliberately turned off (decided 2026-10-29; see the Audio page's own
docstring in `app/api/routes/audio.py`). Deliberately standalone: this
does NOT read or write the `devices` table's `audiofile` column (that
field is master-authoritative config, overwritten by the next automatic
config sync -- see `AudioStatusPublic`'s own comment). Instead, "which
file" and "what volume" live entirely in this module's own JSON state
file, which is also the one place the real `apply_active_state`
implementation (not built yet, Docs/To_Be_Done.md item 7's hardware
step) should read from once it exists, rather than reimplementing mpv
process/IPC handling a second time.

Two independent "which file" slots, both played through the same
`_play_file`/mpv process machinery: `audiofile` (the real show file,
`play()`, "Lecture"/"Fichier actuel") and `test_audiofile` (a
calibration sample, `play_test()`, "Son test") -- kept separate so
testing playback/volume never overwrites the actual configured file.
`loop` is shared by both (there's only ever one mpv process): whichever
file is currently playing repeats via mpv's `--loop-file`/`loop-file`
IPC property when set.

mpv is driven over its JSON IPC socket (https://mpv.io/manual/stable/
master/#json-ipc) rather than one subprocess per command: this lets a
live "set volume" change reach an already-playing mpv instance without
restarting playback. `_start_process`/`_send_ipc_command` are the two
seams tests replace (no real mpv binary or socket needed to exercise
this module's own logic).
"""

import json
import logging
import socket
import subprocess
import time
from pathlib import Path
from typing import Protocol

from app.core.config import settings
from app.models.audio import DEFAULT_VOLUME

logger = logging.getLogger(__name__)

IPC_SOCKET_PATH = "/tmp/appestrio-mpv.sock"
IPC_TIMEOUT_S = 2.0
PROCESS_STOP_TIMEOUT_S = 3.0
# How long to wait after spawning before checking "did it already die" --
# long enough to catch the extremely common "no usable audio output
# device" failure (mpv exits almost immediately), short enough not to
# make every successful Play button click feel sluggish. A process that
# survives this check can still fail later (unplugged speaker, etc) --
# this is a best-effort "fail loud instead of silently playing nothing"
# check, not a guarantee.
EARLY_EXIT_CHECK_DELAY_S = 0.3


class AudioPlayerError(Exception):
    """Raised when there's nothing playable (no audio file configured,
    or the configured file doesn't exist on disk) -- callers (routes)
    should catch this and map it to a clean 4xx response.
    """


class _Process(Protocol):
    stderr: object

    def poll(self) -> int | None: ...
    def terminate(self) -> None: ...
    def kill(self) -> None: ...
    def wait(self, timeout: float | None = None) -> int: ...


_process: _Process | None = None


def _audio_dir() -> Path:
    return Path(settings.AUDIO_DIR)


def _state_path() -> Path:
    return Path(settings.AUDIO_STATE_PATH)


_DEFAULT_STATE = {
    "volume": DEFAULT_VOLUME,
    "audiofile": None,
    "test_audiofile": None,
    "loop": False,
}


def load_state() -> dict:
    path = _state_path()
    if not path.exists():
        return dict(_DEFAULT_STATE)
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        logger.warning("audio_player: couldn't read state file %s, using defaults", path)
        return dict(_DEFAULT_STATE)
    return {
        "volume": data.get("volume", DEFAULT_VOLUME),
        "audiofile": data.get("audiofile"),
        "test_audiofile": data.get("test_audiofile"),
        "loop": data.get("loop", False),
    }


def save_state(
    *, volume: int, audiofile: str | None, test_audiofile: str | None, loop: bool
) -> None:
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "volume": volume,
                "audiofile": audiofile,
                "test_audiofile": test_audiofile,
                "loop": loop,
            }
        )
    )


def is_playing() -> bool:
    return _process is not None and _process.poll() is None


def _start_process(
    args: list[str],
) -> _Process:  # pragma: no cover -- real mpv, not unit-tested
    # stderr is captured (not DEVNULL) so a near-immediate failure --
    # overwhelmingly the most common one being "no usable audio output
    # device," e.g. a container with no /dev/snd passthrough -- can be
    # read back and surfaced instead of silently "playing" nothing.
    return subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def _send_ipc_command(command: list[object]) -> None:  # pragma: no cover -- real socket
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.settimeout(IPC_TIMEOUT_S)
        sock.connect(IPC_SOCKET_PATH)
        sock.sendall(json.dumps({"command": command}).encode("utf-8") + b"\n")


def stop() -> None:
    global _process
    if _process is None:
        return
    if _process.poll() is None:
        _process.terminate()
        try:
            _process.wait(timeout=PROCESS_STOP_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            _process.kill()
            _process.wait(timeout=PROCESS_STOP_TIMEOUT_S)
    _process = None


def _play_file(
    *, target_file: str | None, volume: int, loop: bool, not_configured_message: str
) -> None:
    global _process
    if not target_file:
        raise AudioPlayerError(not_configured_message)

    path = _audio_dir() / target_file
    if not path.is_file():
        raise AudioPlayerError(f"Audio file {target_file!r} not found")

    stop()
    try:
        _process = _start_process(
            [
                "mpv",
                "--no-video",
                f"--volume={volume}",
                f"--loop-file={'inf' if loop else 'no'}",
                f"--input-ipc-server={IPC_SOCKET_PATH}",
                str(path),
            ]
        )
    except OSError as exc:
        raise AudioPlayerError(f"Couldn't start mpv: {exc}") from exc

    time.sleep(EARLY_EXIT_CHECK_DELAY_S)
    if _process.poll() is not None:
        stderr_output = ""
        if _process.stderr is not None:
            stderr_output = _process.stderr.read().decode("utf-8", errors="replace").strip()
        _process = None
        detail = stderr_output or "no error output captured"
        raise AudioPlayerError(f"mpv exited immediately, nothing played: {detail}")


def play() -> None:
    """Plays this device's main configured audio file -- "Fichier
    actuel", set via the main upload slot -- at the persisted volume and
    loop setting. Also the file the real `apply_active_state`
    implementation (not built yet) should eventually use.
    """
    state = load_state()
    _play_file(
        target_file=state["audiofile"],
        volume=state["volume"],
        loop=state["loop"],
        not_configured_message="No audio file configured for this device yet",
    )


def play_test() -> None:
    """Plays the separate "Son test" calibration sample, uploaded via
    its own slot -- deliberately independent of `play()`'s file, so
    testing playback/volume never touches what's actually configured to
    play on this device.
    """
    state = load_state()
    _play_file(
        target_file=state["test_audiofile"],
        volume=state["volume"],
        loop=state["loop"],
        not_configured_message="No test sound uploaded yet",
    )


def set_volume(volume: int) -> None:
    state = load_state()
    save_state(
        volume=volume,
        audiofile=state["audiofile"],
        test_audiofile=state["test_audiofile"],
        loop=state["loop"],
    )
    if is_playing():
        try:
            _send_ipc_command(["set_property", "volume", volume])
        except OSError:
            logger.warning("audio_player: couldn't reach mpv's IPC socket to live-update volume")


def set_loop(enabled: bool) -> None:
    state = load_state()
    save_state(
        volume=state["volume"],
        audiofile=state["audiofile"],
        test_audiofile=state["test_audiofile"],
        loop=enabled,
    )
    if is_playing():
        try:
            _send_ipc_command(["set_property", "loop-file", "inf" if enabled else "no"])
        except OSError:
            logger.warning("audio_player: couldn't reach mpv's IPC socket to live-update loop")
