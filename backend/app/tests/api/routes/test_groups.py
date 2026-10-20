import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import settings
from app.models import Device
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


def test_get_group_includes_devices(client: TestClient, session: Session) -> None:
    group = create_group(session)
    device = client.post(
        DEVICES_URL,
        json=device_payload(group_id=str(group.uuid), handles_audio=True, handles_dmx=False),
    ).json()

    response = client.get(f"{GROUPS_URL}{group.uuid}")

    assert response.status_code == 200
    devices = response.json()["devices"]
    assert len(devices) == 1
    assert devices[0]["device_id"] == device["device_id"]
    assert devices[0]["device_name"] == device["device_name"]
    assert devices[0]["active"] == device["active"]
    assert devices[0]["handles_audio"] is True
    assert devices[0]["handles_dmx"] is False


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

    response = client.request("DELETE", GROUPS_URL, json={"uuids": [created["uuid"]]})
    assert response.status_code == 200
    assert response.json()["message"] == "1 group(s) deleted successfully"

    get_response = client.get(f"{GROUPS_URL}{created['uuid']}")
    assert get_response.status_code == 404


def test_delete_group_not_found(client: TestClient) -> None:
    response = client.request("DELETE", GROUPS_URL, json={"uuids": [str(uuid.uuid4())]})

    assert response.status_code == 404


def test_delete_group_in_use_by_device(client: TestClient, session: Session) -> None:
    group = create_group(session)
    client.post(DEVICES_URL, json=device_payload(group_id=str(group.uuid)))

    response = client.request("DELETE", GROUPS_URL, json={"uuids": [str(group.uuid)]})

    assert response.status_code == 409


def test_delete_groups_requires_at_least_one_uuid(client: TestClient) -> None:
    response = client.request("DELETE", GROUPS_URL, json={"uuids": []})

    assert response.status_code == 422


def test_delete_groups_bulk(client: TestClient) -> None:
    first = client.post(GROUPS_URL, json=group_payload(label="Group A")).json()
    second = client.post(GROUPS_URL, json=group_payload(label="Group B")).json()

    response = client.request(
        "DELETE", GROUPS_URL, json={"uuids": [first["uuid"], second["uuid"]]}
    )

    assert response.status_code == 200
    assert response.json()["message"] == "2 group(s) deleted successfully"
    assert client.get(GROUPS_URL).json()["count"] == 0


def test_delete_groups_bulk_not_found(client: TestClient) -> None:
    created = client.post(GROUPS_URL, json=group_payload()).json()
    missing_uuid = str(uuid.uuid4())

    response = client.request(
        "DELETE", GROUPS_URL, json={"uuids": [created["uuid"], missing_uuid]}
    )

    assert response.status_code == 404
    assert client.get(GROUPS_URL).json()["count"] == 1


def test_set_group_devices(client: TestClient, session: Session) -> None:
    group = create_group(session)
    device = client.post(DEVICES_URL, json=device_payload()).json()

    response = client.patch(
        f"{GROUPS_URL}{group.uuid}/devices",
        json={"device_ids": [device["device_id"]]},
    )

    assert response.status_code == 200
    content = response.json()
    assert content["count"] == 1
    assert content["data"][0]["device_id"] == device["device_id"]
    assert content["data"][0]["group"] == group.label


def test_set_group_devices_unassigns_removed_devices(
    client: TestClient, session: Session
) -> None:
    group = create_group(session)
    device = client.post(
        DEVICES_URL, json=device_payload(group_id=str(group.uuid))
    ).json()

    response = client.patch(
        f"{GROUPS_URL}{group.uuid}/devices", json={"device_ids": []}
    )

    assert response.status_code == 200
    assert response.json()["count"] == 0

    get_device = client.get(f"{DEVICES_URL}{device['device_id']}")
    assert get_device.json()["group"] is None


def test_set_group_devices_with_unknown_device(
    client: TestClient, session: Session
) -> None:
    group = create_group(session)

    response = client.patch(
        f"{GROUPS_URL}{group.uuid}/devices",
        json={"device_ids": ["nosuchdevice"]},
    )

    assert response.status_code == 404


def test_set_group_devices_group_not_found(client: TestClient) -> None:
    response = client.patch(
        f"{GROUPS_URL}{uuid.uuid4()}/devices", json={"device_ids": []}
    )

    assert response.status_code == 404


def _mark_synced(session: Session, device_id: str) -> None:
    """Directly sets synced_version = config_version for a test device --
    no public API does this (it's lora-daemon's own write, via a real
    PONG), so tests that need an "in sync" device fake the end state
    directly on the shared DB, same as lora-daemon would.
    """
    device = session.exec(select(Device).where(Device.device_id == device_id)).one()
    device.synced_version = device.config_version
    session.add(device)
    session.commit()


def test_test_calendar_reports_in_sync_devices(
    client: TestClient, session: Session
) -> None:
    group = create_group(session)
    device_a = client.post(
        DEVICES_URL, json=device_payload(device_type="lumestrio", device_number=1)
    ).json()
    device_b = client.post(
        DEVICES_URL, json=device_payload(device_type="lumestrio", device_number=2)
    ).json()
    client.patch(
        f"{GROUPS_URL}{group.uuid}/devices",
        json={"device_ids": [device_a["device_id"], device_b["device_id"]]},
    )
    _mark_synced(session, device_a["device_id"])
    _mark_synced(session, device_b["device_id"])

    response = client.post(f"{GROUPS_URL}{group.uuid}/test-calendar")

    assert response.status_code == 200
    assert response.json()["message"] == "2 lumestrio device(s) in sync"


def test_test_calendar_reports_pending_devices(
    client: TestClient, session: Session
) -> None:
    group = create_group(session)
    device = client.post(
        DEVICES_URL, json=device_payload(device_type="lumestrio", device_number=1)
    ).json()
    client.patch(
        f"{GROUPS_URL}{group.uuid}/devices",
        json={"device_ids": [device["device_id"]]},
    )
    # Freshly created: config_version=1, synced_version=0 by default --
    # never confirmed applied, so it's pending without any extra setup.

    response = client.post(f"{GROUPS_URL}{group.uuid}/test-calendar")

    assert response.status_code == 200
    assert response.json()["message"] == "0 lumestrio device(s) in sync, 1 pending"


def test_test_calendar_reports_relaystrio_as_skipped(
    client: TestClient, session: Session
) -> None:
    group = create_group(session)
    lumestrio = client.post(
        DEVICES_URL, json=device_payload(device_type="lumestrio", device_number=1)
    ).json()
    relaystrio = client.post(
        DEVICES_URL, json=device_payload(device_type="relaystrio", device_number=1)
    ).json()
    client.patch(
        f"{GROUPS_URL}{group.uuid}/devices",
        json={"device_ids": [lumestrio["device_id"], relaystrio["device_id"]]},
    )
    _mark_synced(session, lumestrio["device_id"])

    response = client.post(f"{GROUPS_URL}{group.uuid}/test-calendar")

    assert response.status_code == 200
    assert response.json()["message"] == (
        "1 lumestrio device(s) in sync, 1 relaystrio skipped (not yet supported)"
    )


def test_test_calendar_group_not_found(client: TestClient) -> None:
    response = client.post(f"{GROUPS_URL}{uuid.uuid4()}/test-calendar")

    assert response.status_code == 404
