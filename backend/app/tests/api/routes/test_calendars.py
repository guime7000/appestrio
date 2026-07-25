import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.tests.utils import calendar_payload, create_calendar, create_group

CALENDARS_URL = f"{settings.API_V1_STR}/calendars/"


def test_create_calendar(client: TestClient) -> None:
    response = client.post(CALENDARS_URL, json=calendar_payload(label="Calendar A"))

    assert response.status_code == 201
    content = response.json()
    assert content["label"] == "Calendar A"
    assert content["presets"]["setup1"]["start_time"] == "09:15"
    assert content["days"]["lundi"] == "setup1"
    assert "uuid" in content
    assert "updated_at" in content


def test_get_calendar(client: TestClient) -> None:
    created = client.post(CALENDARS_URL, json=calendar_payload()).json()

    response = client.get(f"{CALENDARS_URL}{created['uuid']}")

    assert response.status_code == 200
    assert response.json()["uuid"] == created["uuid"]


def test_get_calendar_not_found(client: TestClient) -> None:
    response = client.get(f"{CALENDARS_URL}{uuid.uuid4()}")

    assert response.status_code == 404


def test_list_calendars(client: TestClient) -> None:
    client.post(CALENDARS_URL, json=calendar_payload())
    client.post(CALENDARS_URL, json=calendar_payload())

    response = client.get(CALENDARS_URL)

    assert response.status_code == 200
    content = response.json()
    assert content["count"] == 2
    assert len(content["data"]) == 2


def test_update_calendar(client: TestClient) -> None:
    created = client.post(CALENDARS_URL, json=calendar_payload()).json()

    response = client.patch(
        f"{CALENDARS_URL}{created['uuid']}",
        json={"days": {"lundi": "exception"}},
    )

    assert response.status_code == 200
    content = response.json()
    assert content["days"] == {"lundi": "exception"}
    assert content["label"] == created["label"]


def test_update_calendar_not_found(client: TestClient) -> None:
    response = client.patch(
        f"{CALENDARS_URL}{uuid.uuid4()}", json={"label": "New label"}
    )

    assert response.status_code == 404


def test_delete_calendar(client: TestClient) -> None:
    created = client.post(CALENDARS_URL, json=calendar_payload()).json()

    response = client.delete(f"{CALENDARS_URL}{created['uuid']}")
    assert response.status_code == 200

    get_response = client.get(f"{CALENDARS_URL}{created['uuid']}")
    assert get_response.status_code == 404


def test_delete_calendar_not_found(client: TestClient) -> None:
    response = client.delete(f"{CALENDARS_URL}{uuid.uuid4()}")

    assert response.status_code == 404


def test_delete_calendar_in_use_by_group(client: TestClient, session: Session) -> None:
    calendar = create_calendar(session)
    create_group(session, calendar_id=calendar.uuid)

    response = client.delete(f"{CALENDARS_URL}{calendar.uuid}")

    assert response.status_code == 409
