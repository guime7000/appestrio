from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.services import audio_player
from app.tests.utils import device_payload

AUDIO_URL = f"{settings.API_V1_STR}/audio/"
DEVICES_URL = f"{settings.API_V1_STR}/devices/"


@pytest.fixture(autouse=True)
def _isolate_audio_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "AUDIO_DIR", str(tmp_path / "audio"))
    monkeypatch.setattr(settings, "AUDIO_STATE_PATH", str(tmp_path / "state.json"))
    monkeypatch.setattr(audio_player, "EARLY_EXIT_CHECK_DELAY_S", 0)
    audio_player._process = None


def test_status_reports_handles_audio_false_when_no_device(client: TestClient) -> None:
    response = client.get(f"{AUDIO_URL}status")

    assert response.status_code == 200
    assert response.json()["handles_audio"] is False


def test_status_reports_handles_audio_false_for_non_audio_device(client: TestClient) -> None:
    client.post(DEVICES_URL, json=device_payload(handles_audio=False))

    response = client.get(f"{AUDIO_URL}status")

    assert response.json()["handles_audio"] is False


def test_status_reports_handles_audio_true(client: TestClient) -> None:
    client.post(DEVICES_URL, json=device_payload(handles_audio=True))

    response = client.get(f"{AUDIO_URL}status")

    assert response.status_code == 200
    content = response.json()
    assert content["handles_audio"] is True
    assert content["playing"] is False
    assert content["audiofile"] is None
    assert content["test_audiofile"] is None
    assert content["loop"] is False


def test_status_resolves_masters_own_row_in_a_multi_device_db(client: TestClient) -> None:
    # Master's local DB holds every device (it's the config source for
    # the whole network), not just its own -- unlike a slave, whose DB
    # only ever has its own single row. Master is still itself exactly
    # one physical Pi, found via is_master=True among the others.
    client.post(
        DEVICES_URL, json=device_payload(handles_audio=False, is_master=False, device_number=1)
    )
    client.post(
        DEVICES_URL, json=device_payload(handles_audio=True, is_master=True, device_number=2)
    )

    response = client.get(f"{AUDIO_URL}status")

    assert response.status_code == 200
    assert response.json()["handles_audio"] is True


def test_play_not_found_when_device_not_provisioned(client: TestClient) -> None:
    response = client.post(f"{AUDIO_URL}play")

    assert response.status_code == 404


def test_play_rejected_for_non_audio_device(client: TestClient) -> None:
    client.post(DEVICES_URL, json=device_payload(handles_audio=False))

    response = client.post(f"{AUDIO_URL}play")

    assert response.status_code == 400


def test_play_rejected_when_no_file_uploaded_yet(client: TestClient) -> None:
    client.post(DEVICES_URL, json=device_payload(handles_audio=True))

    response = client.post(f"{AUDIO_URL}play")

    assert response.status_code == 400
    assert "No audio file" in response.json()["detail"]


def test_upload_then_play_then_stop(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    client.post(DEVICES_URL, json=device_payload(handles_audio=True))
    monkeypatch.setattr(audio_player, "_start_process", lambda _args: _FakeProcess())

    upload_response = client.post(
        f"{AUDIO_URL}upload",
        files={"file": ("song.mp3", b"not really audio", "audio/mpeg")},
    )
    assert upload_response.status_code == 200
    assert upload_response.json()["audiofile"] == "song.mp3"

    play_response = client.post(f"{AUDIO_URL}play")
    assert play_response.status_code == 200
    assert play_response.json()["playing"] is True

    stop_response = client.post(f"{AUDIO_URL}stop")
    assert stop_response.status_code == 200
    assert stop_response.json()["playing"] is False


def test_play_test_rejected_when_no_test_sound_uploaded_yet(client: TestClient) -> None:
    client.post(DEVICES_URL, json=device_payload(handles_audio=True))

    response = client.post(f"{AUDIO_URL}test")

    assert response.status_code == 400
    assert "No test sound" in response.json()["detail"]


def test_upload_test_then_son_test_does_not_touch_main_audiofile(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    client.post(DEVICES_URL, json=device_payload(handles_audio=True))
    monkeypatch.setattr(audio_player, "_start_process", lambda _args: _FakeProcess())

    # A main show file is already configured...
    main_upload = client.post(
        f"{AUDIO_URL}upload",
        files={"file": ("show.mp3", b"not really audio", "audio/mpeg")},
    )
    assert main_upload.json()["audiofile"] == "show.mp3"

    # ...uploading and playing a test sound must not change it.
    test_upload = client.post(
        f"{AUDIO_URL}upload-test",
        files={"file": ("tone.mp3", b"beep", "audio/mpeg")},
    )
    assert test_upload.status_code == 200
    assert test_upload.json()["test_audiofile"] == "test/tone.mp3"
    assert test_upload.json()["audiofile"] == "show.mp3"

    play_test_response = client.post(f"{AUDIO_URL}test")
    assert play_test_response.status_code == 200
    assert play_test_response.json()["playing"] is True
    assert play_test_response.json()["audiofile"] == "show.mp3"


def test_upload_test_and_upload_use_separate_files_on_disk(client: TestClient) -> None:
    client.post(DEVICES_URL, json=device_payload(handles_audio=True))

    client.post(
        f"{AUDIO_URL}upload", files={"file": ("same-name.mp3", b"main", "audio/mpeg")}
    )
    client.post(
        f"{AUDIO_URL}upload-test", files={"file": ("same-name.mp3", b"test", "audio/mpeg")}
    )

    audio_dir = Path(settings.AUDIO_DIR)
    assert (audio_dir / "same-name.mp3").read_bytes() == b"main"
    assert (audio_dir / "test" / "same-name.mp3").read_bytes() == b"test"


def test_upload_test_rejects_unsupported_extension(client: TestClient) -> None:
    client.post(DEVICES_URL, json=device_payload(handles_audio=True))

    response = client.post(
        f"{AUDIO_URL}upload-test",
        files={"file": ("tone.exe", b"nope", "application/octet-stream")},
    )

    assert response.status_code == 400


def test_upload_rejects_unsupported_extension(client: TestClient) -> None:
    client.post(DEVICES_URL, json=device_payload(handles_audio=True))

    response = client.post(
        f"{AUDIO_URL}upload",
        files={"file": ("song.exe", b"nope", "application/octet-stream")},
    )

    assert response.status_code == 400


def test_upload_rejects_oversized_file(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    client.post(DEVICES_URL, json=device_payload(handles_audio=True))
    monkeypatch.setattr(settings, "AUDIO_MAX_UPLOAD_BYTES", 4)

    response = client.post(
        f"{AUDIO_URL}upload",
        files={"file": ("song.mp3", b"way too big", "audio/mpeg")},
    )

    assert response.status_code == 413


def test_upload_sanitizes_path_traversal_attempt(client: TestClient, tmp_path: Path) -> None:
    client.post(DEVICES_URL, json=device_payload(handles_audio=True))

    response = client.post(
        f"{AUDIO_URL}upload",
        files={"file": ("../../evil.mp3", b"data", "audio/mpeg")},
    )

    assert response.status_code == 200
    assert response.json()["audiofile"] == "evil.mp3"
    assert (Path(settings.AUDIO_DIR) / "evil.mp3").is_file()
    assert not (tmp_path / "evil.mp3").exists()


def test_volume_updates_state(client: TestClient) -> None:
    client.post(DEVICES_URL, json=device_payload(handles_audio=True))

    response = client.post(f"{AUDIO_URL}volume", json={"volume": 42})

    assert response.status_code == 200
    assert response.json()["volume"] == 42


def test_volume_rejects_out_of_range(client: TestClient) -> None:
    client.post(DEVICES_URL, json=device_payload(handles_audio=True))

    response = client.post(f"{AUDIO_URL}volume", json={"volume": 101})

    assert response.status_code == 422


def test_loop_updates_state(client: TestClient) -> None:
    client.post(DEVICES_URL, json=device_payload(handles_audio=True))

    response = client.post(f"{AUDIO_URL}loop", json={"enabled": True})

    assert response.status_code == 200
    assert response.json()["loop"] is True

    response = client.post(f"{AUDIO_URL}loop", json={"enabled": False})

    assert response.json()["loop"] is False


def test_loop_passed_to_mpv_on_play(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    client.post(DEVICES_URL, json=device_payload(handles_audio=True))
    client.post(
        f"{AUDIO_URL}upload",
        files={"file": ("song.mp3", b"not really audio", "audio/mpeg")},
    )
    client.post(f"{AUDIO_URL}loop", json={"enabled": True})

    seen_args: list[list[str]] = []
    monkeypatch.setattr(
        audio_player,
        "_start_process",
        lambda args: (seen_args.append(args), _FakeProcess())[1],
    )

    response = client.post(f"{AUDIO_URL}play")

    assert response.status_code == 200
    assert "--loop-file=inf" in seen_args[0]


class _FakeProcess:
    stderr = None

    def poll(self) -> int | None:
        return None

    def terminate(self) -> None:
        pass

    def kill(self) -> None:
        pass

    def wait(self, timeout: float | None = None) -> int:
        return 0
