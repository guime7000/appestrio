from pathlib import Path

import pytest

from app.core.config import settings
from app.services import audio_player, relay
from app.services.activation import apply_active_state
from app.services.audio_player import AudioPlayerError


@pytest.fixture(autouse=True)
def _isolate_audio_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "AUDIO_DIR", str(tmp_path / "audio"))
    monkeypatch.setattr(settings, "AUDIO_STATE_PATH", str(tmp_path / "state.json"))
    audio_player._process = None
    relay._device = None
    relay._device_pin = None
    # Real relay.activate() falls back through gpiozero's pin factories
    # and warns loudly when none is available (expected in this
    # sandbox, no real GPIO) -- tests that don't care about the relay
    # call itself get a silent no-op; the ones that do override this.
    monkeypatch.setattr(relay, "activate", lambda _active: None)


def test_apply_active_state_audio_device_plays_the_configured_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[str | None] = []
    monkeypatch.setattr(audio_player, "play", lambda: seen.append("played"))

    apply_active_state(
        device_id="lumestrio3", active=True, handles_audio=True, handles_dmx=False, audiofile="x.mp3"
    )

    assert seen == ["played"]
    assert audio_player.load_state()["audiofile"] == "x.mp3"


def test_apply_active_state_audio_device_activates_the_relay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(audio_player, "play", lambda: None)
    relay_calls: list[bool] = []
    monkeypatch.setattr(relay, "activate", relay_calls.append)

    apply_active_state(
        device_id="lumestrio3", active=True, handles_audio=True, handles_dmx=False, audiofile="x.mp3"
    )

    assert relay_calls == [True]


def test_apply_active_state_audio_device_activates_relay_even_if_playback_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raise() -> None:
        raise AudioPlayerError("no audio device")

    monkeypatch.setattr(audio_player, "play", _raise)
    relay_calls: list[bool] = []
    monkeypatch.setattr(relay, "activate", relay_calls.append)

    apply_active_state(
        device_id="lumestrio3", active=True, handles_audio=True, handles_dmx=False, audiofile="x.mp3"
    )

    assert relay_calls == [True]


def test_apply_active_state_non_audio_device_does_not_touch_the_relay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    relay_calls: list[bool] = []
    monkeypatch.setattr(relay, "activate", relay_calls.append)

    apply_active_state(device_id="lumestrio3", active=True, handles_audio=False, handles_dmx=True)

    assert relay_calls == []


def test_apply_active_state_audio_device_preserves_local_volume_and_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    audio_player.save_state(volume=42, audiofile="old.mp3", test_audiofile="test/tone.mp3", loop=True)
    monkeypatch.setattr(audio_player, "play", lambda: None)

    apply_active_state(
        device_id="lumestrio3", active=True, handles_audio=True, handles_dmx=False, audiofile="new.mp3"
    )

    assert audio_player.load_state() == {
        "volume": 42,
        "audiofile": "new.mp3",
        "test_audiofile": "test/tone.mp3",
        "loop": True,
    }


def test_apply_active_state_audio_device_survives_playback_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raise() -> None:
        raise AudioPlayerError("no audio device")

    monkeypatch.setattr(audio_player, "play", _raise)

    apply_active_state(
        device_id="lumestrio3", active=True, handles_audio=True, handles_dmx=False, audiofile="x.mp3"
    )  # must not raise


def test_apply_active_state_audio_device_without_configured_file_still_tries_to_play(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[str] = []
    monkeypatch.setattr(audio_player, "play", lambda: seen.append("played"))

    apply_active_state(
        device_id="lumestrio3", active=True, handles_audio=True, handles_dmx=False, audiofile=None
    )

    assert seen == ["played"]
    # No `audiofile` provided -- whatever was already persisted (nothing,
    # here) is left alone rather than being overwritten with None.
    assert audio_player.load_state()["audiofile"] is None


def test_apply_active_state_dmx_device_activates_without_raising() -> None:
    apply_active_state(device_id="lumestrio3", active=True, handles_audio=False, handles_dmx=True)


def test_apply_active_state_plain_device_activates_without_raising() -> None:
    apply_active_state(device_id="relaystrio5", active=True, handles_audio=False, handles_dmx=False)


def test_apply_active_state_deactivates_stops_audio_playback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[str] = []
    monkeypatch.setattr(audio_player, "stop", lambda: seen.append("stopped"))

    apply_active_state(device_id="lumestrio3", active=False, handles_audio=True, handles_dmx=True)

    assert seen == ["stopped"]


def test_apply_active_state_deactivates_the_relay(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(audio_player, "stop", lambda: None)
    relay_calls: list[bool] = []
    monkeypatch.setattr(relay, "activate", relay_calls.append)

    apply_active_state(device_id="lumestrio3", active=False, handles_audio=True, handles_dmx=True)

    assert relay_calls == [False]


def test_apply_active_state_deactivates_plain_device_without_raising() -> None:
    apply_active_state(device_id="relaystrio5", active=False, handles_audio=False, handles_dmx=False)
