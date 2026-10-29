from pathlib import Path

import pytest

from app.core.config import settings
from app.services import audio_player


class _FakeStderr:
    def __init__(self, content: bytes = b"") -> None:
        self._content = content

    def read(self) -> bytes:
        return self._content


class _FakeProcess:
    def __init__(self, *, exits_immediately: bool = False, stderr: bytes = b"") -> None:
        self.terminated = False
        self.killed = False
        self._exited = exits_immediately
        self.stderr = _FakeStderr(stderr)

    def poll(self) -> int | None:
        return 0 if self._exited else None

    def terminate(self) -> None:
        self.terminated = True
        self._exited = True

    def kill(self) -> None:
        self.killed = True
        self._exited = True

    def wait(self, timeout: float | None = None) -> int:
        return 0


@pytest.fixture(autouse=True)
def _isolate_audio_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "AUDIO_DIR", str(tmp_path / "audio"))
    monkeypatch.setattr(settings, "AUDIO_STATE_PATH", str(tmp_path / "state.json"))
    # The real delay exists to catch mpv dying right after launch (see
    # its own comment) -- zero it here so tests stay fast; the delay
    # itself isn't this module's logic to test.
    monkeypatch.setattr(audio_player, "EARLY_EXIT_CHECK_DELAY_S", 0)
    audio_player._process = None


def _write_audio_file(name: str = "song.mp3") -> str:
    audio_dir = Path(settings.AUDIO_DIR)
    audio_dir.mkdir(parents=True, exist_ok=True)
    (audio_dir / name).write_bytes(b"not really audio")
    return name


def _set_state(*, volume: int, audiofile: str | None, test_audiofile: str | None = None,
               loop: bool = False) -> None:
    audio_player.save_state(
        volume=volume, audiofile=audiofile, test_audiofile=test_audiofile, loop=loop
    )


def _default_state() -> dict:
    return {
        "volume": audio_player.DEFAULT_VOLUME,
        "audiofile": None,
        "test_audiofile": None,
        "loop": False,
    }


def test_load_state_defaults_when_no_file() -> None:
    assert audio_player.load_state() == _default_state()


def test_save_and_load_state_round_trips() -> None:
    audio_player.save_state(
        volume=42, audiofile="song.mp3", test_audiofile="test/tone.mp3", loop=True
    )

    assert audio_player.load_state() == {
        "volume": 42,
        "audiofile": "song.mp3",
        "test_audiofile": "test/tone.mp3",
        "loop": True,
    }


def test_load_state_recovers_from_corrupt_file() -> None:
    Path(settings.AUDIO_STATE_PATH).parent.mkdir(parents=True, exist_ok=True)
    Path(settings.AUDIO_STATE_PATH).write_text("not json")

    assert audio_player.load_state() == _default_state()


def test_play_raises_when_no_audiofile_configured() -> None:
    with pytest.raises(audio_player.AudioPlayerError, match="No audio file"):
        audio_player.play()


def test_play_raises_when_file_missing_on_disk() -> None:
    _set_state(volume=50, audiofile="missing.mp3")

    with pytest.raises(audio_player.AudioPlayerError, match="not found"):
        audio_player.play()


def test_play_starts_process_at_persisted_file_and_volume(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    name = _write_audio_file()
    _set_state(volume=77, audiofile=name)
    seen_args: list[list[str]] = []

    def _fake_start(args: list[str]) -> _FakeProcess:
        seen_args.append(args)
        return _FakeProcess()

    monkeypatch.setattr(audio_player, "_start_process", _fake_start)

    audio_player.play()

    assert audio_player.is_playing() is True
    assert seen_args[0][-1].endswith(name)
    assert "--volume=77" in seen_args[0]
    assert "--loop-file=no" in seen_args[0]


def test_play_passes_loop_file_inf_when_loop_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    name = _write_audio_file()
    _set_state(volume=50, audiofile=name, loop=True)
    seen_args: list[list[str]] = []
    monkeypatch.setattr(
        audio_player, "_start_process", lambda args: (seen_args.append(args), _FakeProcess())[1]
    )

    audio_player.play()

    assert "--loop-file=inf" in seen_args[0]


def test_play_does_not_touch_test_audiofile(monkeypatch: pytest.MonkeyPatch) -> None:
    name = _write_audio_file()
    _set_state(volume=50, audiofile=name, test_audiofile="test/tone.mp3")
    monkeypatch.setattr(audio_player, "_start_process", lambda _args: _FakeProcess())

    audio_player.play()

    assert audio_player.load_state()["test_audiofile"] == "test/tone.mp3"


def test_play_stops_previous_process_first(monkeypatch: pytest.MonkeyPatch) -> None:
    name = _write_audio_file()
    _set_state(volume=50, audiofile=name)
    processes = [_FakeProcess(), _FakeProcess()]
    monkeypatch.setattr(audio_player, "_start_process", lambda _args: processes.pop(0))

    audio_player.play()
    first = audio_player._process
    audio_player.play()

    assert first.terminated is True


def test_play_raises_with_stderr_when_mpv_exits_immediately(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    name = _write_audio_file()
    _set_state(volume=50, audiofile=name)
    monkeypatch.setattr(
        audio_player,
        "_start_process",
        lambda _args: _FakeProcess(exits_immediately=True, stderr=b"AO: [alsa] no device\n"),
    )

    with pytest.raises(audio_player.AudioPlayerError, match="no device"):
        audio_player.play()

    assert audio_player.is_playing() is False


def test_play_raises_when_mpv_binary_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    name = _write_audio_file()
    _set_state(volume=50, audiofile=name)

    def _raise(_args: list[str]) -> _FakeProcess:
        raise FileNotFoundError("mpv not found")

    monkeypatch.setattr(audio_player, "_start_process", _raise)

    with pytest.raises(audio_player.AudioPlayerError, match="Couldn't start mpv"):
        audio_player.play()


def test_play_test_raises_when_no_test_audiofile_configured() -> None:
    with pytest.raises(audio_player.AudioPlayerError, match="No test sound"):
        audio_player.play_test()


def test_play_test_plays_the_test_slot_not_the_main_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    main_name = _write_audio_file("show.mp3")
    test_name = "test/tone.mp3"
    (Path(settings.AUDIO_DIR) / "test").mkdir(parents=True, exist_ok=True)
    (Path(settings.AUDIO_DIR) / test_name).write_bytes(b"beep")
    _set_state(volume=42, audiofile=main_name, test_audiofile=test_name)
    seen_args: list[list[str]] = []
    monkeypatch.setattr(
        audio_player, "_start_process", lambda args: (seen_args.append(args), _FakeProcess())[1]
    )

    audio_player.play_test()

    assert seen_args[0][-1].endswith(test_name)
    assert "--volume=42" in seen_args[0]
    # play_test never touches the main audiofile.
    assert audio_player.load_state()["audiofile"] == main_name


def test_stop_is_a_noop_when_nothing_playing() -> None:
    audio_player.stop()  # must not raise

    assert audio_player.is_playing() is False


def test_stop_terminates_running_process(monkeypatch: pytest.MonkeyPatch) -> None:
    name = _write_audio_file()
    _set_state(volume=50, audiofile=name)
    monkeypatch.setattr(audio_player, "_start_process", lambda _args: _FakeProcess())
    audio_player.play()

    audio_player.stop()

    assert audio_player.is_playing() is False


def test_set_volume_persists_even_when_not_playing() -> None:
    audio_player.set_volume(10)

    assert audio_player.load_state()["volume"] == 10


def test_set_volume_preserves_both_file_slots_and_loop() -> None:
    _set_state(volume=50, audiofile="show.mp3", test_audiofile="test/tone.mp3", loop=True)

    audio_player.set_volume(10)

    assert audio_player.load_state() == {
        "volume": 10,
        "audiofile": "show.mp3",
        "test_audiofile": "test/tone.mp3",
        "loop": True,
    }


def test_set_volume_sends_ipc_command_when_playing(monkeypatch: pytest.MonkeyPatch) -> None:
    name = _write_audio_file()
    _set_state(volume=50, audiofile=name)
    monkeypatch.setattr(audio_player, "_start_process", lambda _args: _FakeProcess())
    audio_player.play()

    seen_commands = []
    monkeypatch.setattr(audio_player, "_send_ipc_command", seen_commands.append)

    audio_player.set_volume(65)

    assert seen_commands == [["set_property", "volume", 65]]
    assert audio_player.load_state()["volume"] == 65


def test_set_volume_survives_unreachable_ipc_socket(monkeypatch: pytest.MonkeyPatch) -> None:
    name = _write_audio_file()
    _set_state(volume=50, audiofile=name)
    monkeypatch.setattr(audio_player, "_start_process", lambda _args: _FakeProcess())
    audio_player.play()

    def _raise(_command: list[object]) -> None:
        raise OSError("no one's listening")

    monkeypatch.setattr(audio_player, "_send_ipc_command", _raise)

    audio_player.set_volume(65)  # must not raise

    assert audio_player.load_state()["volume"] == 65


def test_set_loop_persists_even_when_not_playing() -> None:
    audio_player.set_loop(True)

    assert audio_player.load_state()["loop"] is True


def test_set_loop_preserves_other_fields() -> None:
    _set_state(volume=50, audiofile="show.mp3", test_audiofile="test/tone.mp3")

    audio_player.set_loop(True)

    assert audio_player.load_state() == {
        "volume": 50,
        "audiofile": "show.mp3",
        "test_audiofile": "test/tone.mp3",
        "loop": True,
    }


def test_set_loop_sends_ipc_command_when_playing(monkeypatch: pytest.MonkeyPatch) -> None:
    name = _write_audio_file()
    _set_state(volume=50, audiofile=name)
    monkeypatch.setattr(audio_player, "_start_process", lambda _args: _FakeProcess())
    audio_player.play()

    seen_commands = []
    monkeypatch.setattr(audio_player, "_send_ipc_command", seen_commands.append)

    audio_player.set_loop(True)
    audio_player.set_loop(False)

    assert seen_commands == [
        ["set_property", "loop-file", "inf"],
        ["set_property", "loop-file", "no"],
    ]


def test_set_loop_survives_unreachable_ipc_socket(monkeypatch: pytest.MonkeyPatch) -> None:
    name = _write_audio_file()
    _set_state(volume=50, audiofile=name)
    monkeypatch.setattr(audio_player, "_start_process", lambda _args: _FakeProcess())
    audio_player.play()

    def _raise(_command: list[object]) -> None:
        raise OSError("no one's listening")

    monkeypatch.setattr(audio_player, "_send_ipc_command", _raise)

    audio_player.set_loop(True)  # must not raise

    assert audio_player.load_state()["loop"] is True
