import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.services import lora_daemon_client
from app.services.lora_daemon_client import LoraDaemonError

LORA_SETTINGS_URL = f"{settings.API_V1_STR}/lora-settings/"


def test_get_lora_settings_defaults(client: TestClient) -> None:
    response = client.get(LORA_SETTINGS_URL)

    assert response.status_code == 200
    content = response.json()
    assert content["is_active"] is False
    # channel=0/speed=2 match relaystrio's fixed-in-firmware E32 config --
    # see app/models/lora_settings.py's comment.
    assert content["channel"] == 0
    assert content["speed"] == 2
    assert content["fec"] is True
    assert content["ping_interval_s"] == 5
    assert content["clock_interval_s"] == 60
    assert content["relaystrio_recurring_threshold_days"] == 2
    assert "id" not in content


def test_update_lora_settings(client: TestClient) -> None:
    response = client.patch(LORA_SETTINGS_URL, json={"channel": 12, "is_active": True})

    assert response.status_code == 200
    content = response.json()
    assert content["channel"] == 12
    assert content["is_active"] is True
    # Untouched fields keep their value: PATCH is partial.
    assert content["speed"] == 2


def test_update_lora_settings_relaystrio_recurring_threshold(client: TestClient) -> None:
    response = client.patch(
        LORA_SETTINGS_URL, json={"relaystrio_recurring_threshold_days": 30}
    )

    assert response.status_code == 200
    assert response.json()["relaystrio_recurring_threshold_days"] == 30


def test_update_lora_settings_rejects_non_positive_relaystrio_recurring_threshold(
    client: TestClient,
) -> None:
    response = client.patch(
        LORA_SETTINGS_URL, json={"relaystrio_recurring_threshold_days": 0}
    )

    assert response.status_code == 422


def test_update_lora_settings_rejects_out_of_range_channel(client: TestClient) -> None:
    response = client.patch(LORA_SETTINGS_URL, json={"channel": 55})

    assert response.status_code == 422


def test_update_lora_settings_rejects_out_of_range_speed(client: TestClient) -> None:
    response = client.patch(LORA_SETTINGS_URL, json={"speed": 6})

    assert response.status_code == 422


def test_update_lora_settings_rejects_zero_ping_interval(client: TestClient) -> None:
    response = client.patch(LORA_SETTINGS_URL, json={"ping_interval_s": 0})

    assert response.status_code == 422


def test_sync_clocks_now(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []
    monkeypatch.setattr(
        lora_daemon_client, "trigger_clock_sync", lambda: calls.append(1) or {"sent": True}
    )

    response = client.post(f"{LORA_SETTINGS_URL}sync-now")

    assert response.status_code == 200
    assert response.json() == {"message": "Clock sync sent"}
    assert calls == [1]


def test_sync_clocks_now_maps_lora_daemon_error_to_502(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _raise() -> None:
        raise LoraDaemonError("connection refused")

    monkeypatch.setattr(lora_daemon_client, "trigger_clock_sync", _raise)

    response = client.post(f"{LORA_SETTINGS_URL}sync-now")

    assert response.status_code == 502
    assert "connection refused" in response.json()["detail"]
