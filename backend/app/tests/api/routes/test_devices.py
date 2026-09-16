import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.tests.utils import create_calendar, create_group, device_payload

DEVICES_URL = f"{settings.API_V1_STR}/devices/"


def test_create_device(client: TestClient) -> None:
    response = client.post(DEVICES_URL, json=device_payload(device_number=13))

    assert response.status_code == 201
    content = response.json()
    assert content["device_id"] == "lumestrio13"
    assert content["device_name"] == "Le 13e lumestrio"
    assert content["group"] is None
    assert content["group_id"] is None
    assert content["calendar"] is None
    assert content["is_master"] is False
    assert "uuid" not in content
    assert "updated_at" in content


def test_create_device_rejects_negative_device_number(client: TestClient) -> None:
    response = client.post(DEVICES_URL, json=device_payload(device_number=-1))

    assert response.status_code == 422


def test_create_device_rejects_device_number_at_or_above_ceiling(client: TestClient) -> None:
    response = client.post(DEVICES_URL, json=device_payload(device_number=32))

    assert response.status_code == 422


def test_patch_cannot_change_device_id(client: TestClient) -> None:
    created = client.post(DEVICES_URL, json=device_payload()).json()

    response = client.patch(
        f"{DEVICES_URL}{created['device_id']}", json={"device_id": "somethingelse"}
    )

    assert response.status_code == 200
    assert response.json()["device_id"] == created["device_id"]


def test_free_devices_id_excludes_taken_numbers(client: TestClient) -> None:
    client.post(DEVICES_URL, json=device_payload(device_type="lumestrio", device_number=0))
    client.post(DEVICES_URL, json=device_payload(device_type="relaystrio", device_number=3))

    response = client.get(f"{DEVICES_URL}free_devices_id")

    assert response.status_code == 200
    content = response.json()
    assert 0 not in content["lumestrio"]
    assert 1 in content["lumestrio"]
    assert 3 not in content["relaystrio"]
    assert 0 in content["relaystrio"]


def test_pending_sync_lists_newly_created_devices(client: TestClient) -> None:
    created = client.post(DEVICES_URL, json=device_payload()).json()

    response = client.get(f"{DEVICES_URL}pending-sync")

    assert response.status_code == 200
    content = response.json()
    assert content["count"] == 1
    assert content["device_ids"] == [created["device_id"]]


def test_pending_sync_empty_when_no_devices(client: TestClient) -> None:
    response = client.get(f"{DEVICES_URL}pending-sync")

    assert response.status_code == 200
    assert response.json() == {"count": 0, "device_ids": []}


def test_create_device_duplicate_device_id(client: TestClient) -> None:
    payload = device_payload(device_number=13)
    client.post(DEVICES_URL, json=payload)

    response = client.post(DEVICES_URL, json=payload)

    assert response.status_code == 409


def test_create_device_second_master_conflicts(client: TestClient) -> None:
    client.post(DEVICES_URL, json=device_payload(is_master=True))

    response = client.post(DEVICES_URL, json=device_payload(is_master=True))

    assert response.status_code == 409
    assert response.json()["detail"] == "Another device is already the master"


def test_update_device_to_master_conflicts_with_existing_master(
    client: TestClient,
) -> None:
    client.post(DEVICES_URL, json=device_payload(is_master=True))
    other = client.post(DEVICES_URL, json=device_payload()).json()

    response = client.patch(
        f"{DEVICES_URL}{other['device_id']}", json={"is_master": True}
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Another device is already the master"


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
    assert content["group_id"] == str(group.uuid)
    assert content["calendar"]["uuid"] == str(calendar.uuid)


def test_get_device(client: TestClient) -> None:
    created = client.post(DEVICES_URL, json=device_payload()).json()

    response = client.get(f"{DEVICES_URL}{created['device_id']}")

    assert response.status_code == 200
    assert response.json()["device_id"] == created["device_id"]


def test_get_device_not_found(client: TestClient) -> None:
    response = client.get(f"{DEVICES_URL}nosuchdevice")

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
        f"{DEVICES_URL}{created['device_id']}", json={"audiofile": "new_audio.mp3"}
    )

    assert response.status_code == 200
    content = response.json()
    assert content["audiofile"] == "new_audio.mp3"
    assert content["device_name"] == created["device_name"]


def test_update_device_not_found(client: TestClient) -> None:
    response = client.patch(
        f"{DEVICES_URL}nosuchdevice", json={"audiofile": "new_audio.mp3"}
    )

    assert response.status_code == 404


def test_delete_device(client: TestClient) -> None:
    created = client.post(DEVICES_URL, json=device_payload()).json()

    response = client.request(
        "DELETE", DEVICES_URL, json={"device_ids": [created["device_id"]]}
    )
    assert response.status_code == 200
    assert response.json()["message"] == "1 device(s) deleted successfully"

    get_response = client.get(f"{DEVICES_URL}{created['device_id']}")
    assert get_response.status_code == 404


def test_delete_device_not_found(client: TestClient) -> None:
    response = client.request(
        "DELETE", DEVICES_URL, json={"device_ids": ["nosuchdevice"]}
    )

    assert response.status_code == 404


def test_delete_devices_requires_at_least_one_uuid(client: TestClient) -> None:
    response = client.request("DELETE", DEVICES_URL, json={"device_ids": []})

    assert response.status_code == 422


def test_delete_devices_bulk(client: TestClient) -> None:
    first = client.post(DEVICES_URL, json=device_payload(device_number=1)).json()
    second = client.post(DEVICES_URL, json=device_payload(device_number=2)).json()

    response = client.request(
        "DELETE",
        DEVICES_URL,
        json={"device_ids": [first["device_id"], second["device_id"]]},
    )

    assert response.status_code == 200
    assert response.json()["message"] == "2 device(s) deleted successfully"
    assert client.get(DEVICES_URL).json()["count"] == 0


def test_delete_devices_bulk_not_found(client: TestClient) -> None:
    created = client.post(DEVICES_URL, json=device_payload()).json()

    response = client.request(
        "DELETE",
        DEVICES_URL,
        json={"device_ids": [created["device_id"], "nosuchdevice"]},
    )

    assert response.status_code == 404
    assert client.get(DEVICES_URL).json()["count"] == 1
