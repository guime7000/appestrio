import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.tests.utils import create_calendar, create_group, device_payload, group_payload

GROUPS_URL = f"{settings.API_V1_STR}/groups/"
DEVICES_URL = f"{settings.API_V1_STR}/devices/"


def test_create_group(client: TestClient) -> None:
    response = client.post(GROUPS_URL, json=group_payload(label="Group A"))

    assert response.status_code == 201
    content = response.json()
    assert content["label"] == "Group A"
    assert content["calendar_id"] is None
    assert "uuid" in content
    assert "updated_at" in content


def test_create_group_with_unknown_calendar(client: TestClient) -> None:
    response = client.post(
        GROUPS_URL, json=group_payload(calendar_id=str(uuid.uuid4()))
    )

    assert response.status_code == 404


def test_create_group_with_calendar(client: TestClient, session: Session) -> None:
    calendar = create_calendar(session)

    response = client.post(
        GROUPS_URL, json=group_payload(calendar_id=str(calendar.uuid))
    )

    assert response.status_code == 201
    assert response.json()["calendar_id"] == str(calendar.uuid)


def test_get_group(client: TestClient) -> None:
    created = client.post(GROUPS_URL, json=group_payload()).json()

    response = client.get(f"{GROUPS_URL}{created['uuid']}")

    assert response.status_code == 200
    assert response.json()["uuid"] == created["uuid"]


def test_get_group_not_found(client: TestClient) -> None:
    response = client.get(f"{GROUPS_URL}{uuid.uuid4()}")

    assert response.status_code == 404


def test_list_groups(client: TestClient) -> None:
    client.post(GROUPS_URL, json=group_payload())
    client.post(GROUPS_URL, json=group_payload())

    response = client.get(GROUPS_URL)

    assert response.status_code == 200
    content = response.json()
    assert content["count"] == 2
    assert len(content["data"]) == 2


def test_update_group(client: TestClient, session: Session) -> None:
    created = client.post(GROUPS_URL, json=group_payload()).json()
    calendar = create_calendar(session)

    response = client.patch(
        f"{GROUPS_URL}{created['uuid']}", json={"calendar_id": str(calendar.uuid)}
    )

    assert response.status_code == 200
    content = response.json()
    assert content["calendar_id"] == str(calendar.uuid)
    assert content["label"] == created["label"]


def test_update_group_with_unknown_calendar(client: TestClient) -> None:
    created = client.post(GROUPS_URL, json=group_payload()).json()

    response = client.patch(
        f"{GROUPS_URL}{created['uuid']}", json={"calendar_id": str(uuid.uuid4())}
    )

    assert response.status_code == 404


def test_update_group_not_found(client: TestClient) -> None:
    response = client.patch(f"{GROUPS_URL}{uuid.uuid4()}", json={"label": "New label"})

    assert response.status_code == 404


def test_delete_group(client: TestClient) -> None:
    created = client.post(GROUPS_URL, json=group_payload()).json()

    response = client.delete(f"{GROUPS_URL}{created['uuid']}")
    assert response.status_code == 200

    get_response = client.get(f"{GROUPS_URL}{created['uuid']}")
    assert get_response.status_code == 404


def test_delete_group_not_found(client: TestClient) -> None:
    response = client.delete(f"{GROUPS_URL}{uuid.uuid4()}")

    assert response.status_code == 404


def test_delete_group_in_use_by_device(client: TestClient, session: Session) -> None:
    group = create_group(session)
    client.post(DEVICES_URL, json=device_payload(group_id=str(group.uuid)))

    response = client.delete(f"{GROUPS_URL}{group.uuid}")

    assert response.status_code == 409


def test_set_group_devices(client: TestClient, session: Session) -> None:
    group = create_group(session)
    device = client.post(DEVICES_URL, json=device_payload()).json()

    response = client.patch(
        f"{GROUPS_URL}{group.uuid}/devices",
        json={"device_uuids": [device["uuid"]]},
    )

    assert response.status_code == 200
    content = response.json()
    assert content["count"] == 1
    assert content["data"][0]["uuid"] == device["uuid"]
    assert content["data"][0]["group"] == group.label


def test_set_group_devices_unassigns_removed_devices(
    client: TestClient, session: Session
) -> None:
    group = create_group(session)
    device = client.post(
        DEVICES_URL, json=device_payload(group_id=str(group.uuid))
    ).json()

    response = client.patch(
        f"{GROUPS_URL}{group.uuid}/devices", json={"device_uuids": []}
    )

    assert response.status_code == 200
    assert response.json()["count"] == 0

    get_device = client.get(f"{DEVICES_URL}{device['uuid']}")
    assert get_device.json()["group"] is None


def test_set_group_devices_with_unknown_device(
    client: TestClient, session: Session
) -> None:
    group = create_group(session)

    response = client.patch(
        f"{GROUPS_URL}{group.uuid}/devices",
        json={"device_uuids": [str(uuid.uuid4())]},
    )

    assert response.status_code == 404


def test_set_group_devices_group_not_found(client: TestClient) -> None:
    response = client.patch(
        f"{GROUPS_URL}{uuid.uuid4()}/devices", json={"device_uuids": []}
    )

    assert response.status_code == 404
