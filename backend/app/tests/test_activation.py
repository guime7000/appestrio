from pathlib import Path

import pytest

from app.core.config import settings
from app.services import audio_player, dmx_player, relay
from app.services.activation import apply_active_state
from app.services.audio_player import AudioPlayerError
from app.services.dmx_player import DmxPlayerError


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
    # Real dmx_player.start_show()/stop_show() open a real network
    # connection to "qlcplus:9999" -- not reachable in this sandbox
    # (DmxPlayerError, handled the same way a real device with
    # compose.dmx.yml not included would see it). Tests that care about
    # the DMX call itself override this.
    monkeypatch.setattr(dmx_player, "start_show", lambda: None)
    monkeypatch.setattr(dmx_player, "stop_show", lambda: None)


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


def test_apply_active_state_activates_the_relay_even_without_audio(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Decided 2026-11-03: the relay is driven unconditionally by
    # ACTIVATE/DEACTIVATE itself, not gated by `handles_audio` -- every
    # lumestrio runs the same generic image regardless of which
    # capabilities it actually uses.
    relay_calls: list[bool] = []
    monkeypatch.setattr(relay, "activate", relay_calls.append)

    apply_active_state(device_id="lumestrio3", active=True, handles_audio=False, handles_dmx=True)

    assert relay_calls == [True]


def test_apply_active_state_activates_the_relay_for_a_plain_device(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    relay_calls: list[bool] = []
    monkeypatch.setattr(relay, "activate", relay_calls.append)

    apply_active_state(device_id="relaystrio5", active=True, handles_audio=False, handles_dmx=False)

    assert relay_calls == [True]


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


def test_apply_active_state_dmx_device_starts_the_qlc_show(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []
    monkeypatch.setattr(dmx_player, "start_show", lambda: seen.append("started"))

    apply_active_state(device_id="lumestrio3", active=True, handles_audio=False, handles_dmx=True)

    assert seen == ["started"]


def test_apply_active_state_dmx_device_survives_qlc_unreachable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raise() -> None:
        raise DmxPlayerError("couldn't connect to QLC+")

    monkeypatch.setattr(dmx_player, "start_show", _raise)

    apply_active_state(
        device_id="lumestrio3", active=True, handles_audio=False, handles_dmx=True
    )  # must not raise


def test_apply_active_state_non_dmx_device_does_not_touch_qlc(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[str] = []
    monkeypatch.setattr(dmx_player, "start_show", lambda: seen.append("started"))

    apply_active_state(device_id="lumestrio3", active=True, handles_audio=True, handles_dmx=False)

    assert seen == []


def test_apply_active_state_plain_device_activates_without_raising() -> None:
    apply_active_state(device_id="relaystrio5", active=True, handles_audio=False, handles_dmx=False)


def test_apply_active_state_deactivates_stops_audio_playback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[str] = []
    monkeypatch.setattr(audio_player, "stop", lambda: seen.append("stopped"))

    apply_active_state(device_id="lumestrio3", active=False, handles_audio=True, handles_dmx=True)

    assert seen == ["stopped"]


def test_apply_active_state_deactivates_stops_the_qlc_show(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []
    monkeypatch.setattr(dmx_player, "stop_show", lambda: seen.append("stopped"))

    apply_active_state(device_id="lumestrio3", active=False, handles_audio=False, handles_dmx=True)

    assert seen == ["stopped"]


def test_apply_active_state_deactivates_the_relay(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(audio_player, "stop", lambda: None)
    relay_calls: list[bool] = []
    monkeypatch.setattr(relay, "activate", relay_calls.append)

    apply_active_state(device_id="lumestrio3", active=False, handles_audio=True, handles_dmx=True)

    assert relay_calls == [False]


def test_apply_active_state_deactivates_the_relay_for_a_plain_device(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    relay_calls: list[bool] = []
    monkeypatch.setattr(relay, "activate", relay_calls.append)

    apply_active_state(device_id="relaystrio5", active=False, handles_audio=False, handles_dmx=False)

    assert relay_calls == [False]


def test_apply_active_state_deactivates_plain_device_without_raising() -> None:
    apply_active_state(device_id="relaystrio5", active=False, handles_audio=False, handles_dmx=False)


def test_apply_active_state_device_with_both_capabilities_starts_mpv_and_the_qlc_show(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[str] = []
    monkeypatch.setattr(audio_player, "play", lambda: seen.append("audio"))
    monkeypatch.setattr(dmx_player, "start_show", lambda: seen.append("dmx"))

    apply_active_state(
        device_id="lumestrio3", active=True, handles_audio=True, handles_dmx=True, audiofile="x.mp3"
    )

    assert seen == ["dmx", "audio"]
