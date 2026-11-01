from fastapi.testclient import TestClient

from app.core.config import settings
from app.tests.utils import device_payload

DMX_URL = f"{settings.API_V1_STR}/dmx/"
DEVICES_URL = f"{settings.API_V1_STR}/devices/"


def test_status_reports_handles_dmx_false_when_no_device(client: TestClient) -> None:
    response = client.get(f"{DMX_URL}status")

    assert response.status_code == 200
    assert response.json()["handles_dmx"] is False


def test_status_reports_handles_dmx_false_for_non_dmx_device(client: TestClient) -> None:
    client.post(DEVICES_URL, json=device_payload(handles_dmx=False))

    response = client.get(f"{DMX_URL}status")

    assert response.json()["handles_dmx"] is False


def test_status_reports_handles_dmx_true(client: TestClient) -> None:
    client.post(DEVICES_URL, json=device_payload(handles_dmx=True))

    response = client.get(f"{DMX_URL}status")

    assert response.status_code == 200
    assert response.json()["handles_dmx"] is True


def test_status_resolves_masters_own_row_in_a_multi_device_db(client: TestClient) -> None:
    client.post(
        DEVICES_URL, json=device_payload(handles_dmx=False, is_master=False, device_number=1)
    )
    client.post(
        DEVICES_URL, json=device_payload(handles_dmx=True, is_master=True, device_number=2)
    )

    response = client.get(f"{DMX_URL}status")

    assert response.status_code == 200
    assert response.json()["handles_dmx"] is True
