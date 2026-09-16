from fastapi.testclient import TestClient

from app.core.config import settings

LORA_SETTINGS_URL = f"{settings.API_V1_STR}/lora-settings/"


def test_get_lora_settings_defaults(client: TestClient) -> None:
    response = client.get(LORA_SETTINGS_URL)

    assert response.status_code == 200
    content = response.json()
    assert content["is_active"] is False
    assert content["channel"] == 40
    assert content["speed"] == 3
    assert content["fec"] is True
    assert content["ping_interval_s"] == 5
    assert content["clock_interval_s"] == 60
    assert "id" not in content


def test_update_lora_settings(client: TestClient) -> None:
    response = client.patch(LORA_SETTINGS_URL, json={"channel": 12, "is_active": True})

    assert response.status_code == 200
    content = response.json()
    assert content["channel"] == 12
    assert content["is_active"] is True
    # Untouched fields keep their value: PATCH is partial.
    assert content["speed"] == 3


def test_update_lora_settings_rejects_out_of_range_channel(client: TestClient) -> None:
    response = client.patch(LORA_SETTINGS_URL, json={"channel": 55})

    assert response.status_code == 422


def test_update_lora_settings_rejects_out_of_range_speed(client: TestClient) -> None:
    response = client.patch(LORA_SETTINGS_URL, json={"speed": 6})

    assert response.status_code == 422


def test_update_lora_settings_rejects_zero_ping_interval(client: TestClient) -> None:
    response = client.patch(LORA_SETTINGS_URL, json={"ping_interval_s": 0})

    assert response.status_code == 422
