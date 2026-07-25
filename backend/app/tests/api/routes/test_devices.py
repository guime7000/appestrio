import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.tests.utils import create_calendar, create_group, device_payload

DEVICES_URL = f"{settings.API_V1_STR}/devices/"


def test_create_device(client: TestClient) -> None:
    response = client.post(DEVICES_URL, json=device_payload(device_id="lumestrio13"))

    assert response.status_code == 201
    content = response.json()
    assert content["device_id"] == "lumestrio13"
    assert content["device_name"] == "Le 13e lumestrio"
    assert content["group"] is None
    assert content["calendar"] is None
    assert "uuid" in content
    assert "updated_at" in content


def test_create_device_duplicate_device_id(client: TestClient) -> None:
    payload = device_payload(device_id="lumestrio13")
    client.post(DEVICES_URL, json=payload)

    response = client.post(DEVICES_URL, json=payload)

    assert response.status_code == 409


def test_create_device_with_unknown_group(client: TestClient) -> None:
    payload = device_payload(group_id=str(uuid.uuid4()))

    response = client.post(DEVICES_URL, json=payload)

    assert response.status_code == 404


def test_create_device_with_group_and_calendar(
    client: TestClient, session: Session
) -> None:
    calendar = create_calendar(session)
    group = create_group(session, calendar_id=calendar.uuid, label="group A")

    response = client.post(
        DEVICES_URL, json=device_payload(group_id=str(group.uuid))
    )

    assert response.status_code == 201
    content = response.json()
    assert content["group"] == "group A"
    assert content["calendar"]["uuid"] == str(calendar.uuid)


def test_get_device(client: TestClient) -> None:
    created = client.post(DEVICES_URL, json=device_payload()).json()

    response = client.get(f"{DEVICES_URL}{created['uuid']}")

    assert response.status_code == 200
    assert response.json()["uuid"] == created["uuid"]


def test_get_device_not_found(client: TestClient) -> None:
    response = client.get(f"{DEVICES_URL}{uuid.uuid4()}")

    assert response.status_code == 404


def test_list_devices(client: TestClient) -> None:
    client.post(DEVICES_URL, json=device_payload())
    client.post(DEVICES_URL, json=device_payload())

    response = client.get(DEVICES_URL)

    assert response.status_code == 200
    content = response.json()
    assert content["count"] == 2
    assert len(content["data"]) == 2


def test_update_device(client: TestClient) -> None:
    created = client.post(DEVICES_URL, json=device_payload()).json()

    response = client.patch(
        f"{DEVICES_URL}{created['uuid']}", json={"audiofile": "new_audio.mp3"}
    )

    assert response.status_code == 200
    content = response.json()
    assert content["audiofile"] == "new_audio.mp3"
    assert content["device_name"] == created["device_name"]


def test_update_device_not_found(client: TestClient) -> None:
    response = client.patch(
        f"{DEVICES_URL}{uuid.uuid4()}", json={"audiofile": "new_audio.mp3"}
    )

    assert response.status_code == 404


def test_delete_device(client: TestClient) -> None:
    created = client.post(DEVICES_URL, json=device_payload()).json()

    response = client.delete(f"{DEVICES_URL}{created['uuid']}")
    assert response.status_code == 200

    get_response = client.get(f"{DEVICES_URL}{created['uuid']}")
    assert get_response.status_code == 404


def test_delete_device_not_found(client: TestClient) -> None:
    response = client.delete(f"{DEVICES_URL}{uuid.uuid4()}")

    assert response.status_code == 404
