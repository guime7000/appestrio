import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.tests.utils import (
    calendar_payload,
    create_calendar,
    create_group,
    create_ignition_preset,
    ignition_preset_payload,
)

CALENDARS_URL = f"{settings.API_V1_STR}/calendars/"
IGNITION_PRESETS_URL = f"{settings.API_V1_STR}/ignition-presets/"


def test_create_calendar(client: TestClient) -> None:
    response = client.post(
        CALENDARS_URL, json=calendar_payload(label="Calendar A", weekdays=[1, 3, 5])
    )

    assert response.status_code == 201
    content = response.json()
    assert content["label"] == "Calendar A"
    assert content["weekdays"] == [1, 3, 5]
    assert "uuid" in content
    assert "updated_at" in content


def test_create_calendar_defaults_weekdays_to_empty(client: TestClient) -> None:
    payload = calendar_payload()
    del payload["weekdays"]

    response = client.post(CALENDARS_URL, json=payload)

    assert response.status_code == 201
    assert response.json()["weekdays"] == []


def test_create_calendar_rejects_invalid_weekday(client: TestClient) -> None:
    response = client.post(CALENDARS_URL, json=calendar_payload(weekdays=[0]))

    assert response.status_code == 422


def test_list_calendars_only_exposes_summary_fields(client: TestClient) -> None:
    client.post(CALENDARS_URL, json=calendar_payload(label="Calendar A"))

    response = client.get(CALENDARS_URL)

    assert response.status_code == 200
    entry = response.json()["data"][0]
    assert set(entry.keys()) == {"uuid", "label", "updated_at"}
    assert entry["label"] == "Calendar A"


def test_get_calendar_exposes_full_payload_with_ignition_presets(
    client: TestClient, session: Session
) -> None:
    created = client.post(
        CALENDARS_URL, json=calendar_payload(label="Calendar A")
    ).json()
    create_ignition_preset(session, calendar_id=uuid.UUID(created["uuid"]), name="preset A")

    response = client.get(f"{CALENDARS_URL}{created['uuid']}")

    assert response.status_code == 200
    content = response.json()
    assert content["label"] == "Calendar A"
    assert "updated_at" in content
    assert len(content["ignition_presets"]) == 1
    assert content["ignition_presets"][0]["name"] == "preset A"


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


def test_duplicate_calendar(client: TestClient, session: Session) -> None:
    created = client.post(
        CALENDARS_URL, json=calendar_payload(label="calendar_example")
    ).json()
    create_ignition_preset(session, calendar_id=uuid.UUID(created["uuid"]), name="preset A")

    response = client.post(f"{CALENDARS_URL}{created['uuid']}/duplicate")

    assert response.status_code == 201
    content = response.json()
    assert content["uuid"] != created["uuid"]
    assert content["label"] == "calendar_example copy"
    assert content["weekdays"] == created["weekdays"]
    assert len(content["ignition_presets"]) == 1
    assert content["ignition_presets"][0]["name"] == "preset A"
    assert content["ignition_presets"][0]["uuid"] != created["uuid"]

    list_response = client.get(CALENDARS_URL)
    assert list_response.json()["count"] == 2


def test_duplicate_calendar_not_found(client: TestClient) -> None:
    response = client.post(f"{CALENDARS_URL}{uuid.uuid4()}/duplicate")

    assert response.status_code == 404


def test_update_calendar(client: TestClient) -> None:
    created = client.post(CALENDARS_URL, json=calendar_payload()).json()

    response = client.patch(
        f"{CALENDARS_URL}{created['uuid']}",
        json={"weekdays": [6, 7]},
    )

    assert response.status_code == 200
    content = response.json()
    assert content["weekdays"] == [6, 7]
    assert content["label"] == created["label"]


def test_update_calendar_not_found(client: TestClient) -> None:
    response = client.patch(
        f"{CALENDARS_URL}{uuid.uuid4()}", json={"label": "New label"}
    )

    assert response.status_code == 404


def test_delete_calendar(client: TestClient) -> None:
    created = client.post(CALENDARS_URL, json=calendar_payload()).json()

    response = client.request(
        "DELETE", CALENDARS_URL, json={"uuids": [created["uuid"]]}
    )
    assert response.status_code == 200
    assert response.json()["message"] == "1 calendar(s) deleted successfully"

    get_response = client.get(f"{CALENDARS_URL}{created['uuid']}")
    assert get_response.status_code == 404


def test_delete_calendar_cascades_to_ignition_presets(
    client: TestClient, session: Session
) -> None:
    created = client.post(CALENDARS_URL, json=calendar_payload()).json()
    preset = create_ignition_preset(session, calendar_id=uuid.UUID(created["uuid"]))

    client.request("DELETE", CALENDARS_URL, json={"uuids": [created["uuid"]]})

    response = client.get(f"{IGNITION_PRESETS_URL}{preset.uuid}")
    assert response.status_code == 404


def test_delete_calendar_not_found(client: TestClient) -> None:
    response = client.request(
        "DELETE", CALENDARS_URL, json={"uuids": [str(uuid.uuid4())]}
    )

    assert response.status_code == 404


def test_delete_calendar_in_use_by_group(client: TestClient, session: Session) -> None:
    calendar = create_calendar(session)
    create_group(session, calendar_id=calendar.uuid)

    response = client.request(
        "DELETE", CALENDARS_URL, json={"uuids": [str(calendar.uuid)]}
    )

    assert response.status_code == 409


def test_delete_calendars_requires_at_least_one_uuid(client: TestClient) -> None:
    response = client.request("DELETE", CALENDARS_URL, json={"uuids": []})

    assert response.status_code == 422


def test_delete_calendars_bulk(client: TestClient) -> None:
    first = client.post(CALENDARS_URL, json=calendar_payload(label="Calendar A")).json()
    second = client.post(CALENDARS_URL, json=calendar_payload(label="Calendar B")).json()

    response = client.request(
        "DELETE",
        CALENDARS_URL,
        json={"uuids": [first["uuid"], second["uuid"]]},
    )

    assert response.status_code == 200
    assert response.json()["message"] == "2 calendar(s) deleted successfully"
    assert client.get(CALENDARS_URL).json()["count"] == 0


def test_delete_calendars_bulk_not_found(client: TestClient) -> None:
    created = client.post(CALENDARS_URL, json=calendar_payload()).json()
    missing_uuid = str(uuid.uuid4())

    response = client.request(
        "DELETE",
        CALENDARS_URL,
        json={"uuids": [created["uuid"], missing_uuid]},
    )

    assert response.status_code == 404
    # nothing should be deleted when part of the batch is invalid
    assert client.get(CALENDARS_URL).json()["count"] == 1


def test_create_ignition_preset(client: TestClient) -> None:
    calendar = client.post(CALENDARS_URL, json=calendar_payload()).json()

    response = client.post(
        IGNITION_PRESETS_URL, json=ignition_preset_payload(calendar["uuid"])
    )

    assert response.status_code == 201
    content = response.json()
    assert content["calendar_id"] == calendar["uuid"]
    assert content["start_date"] == "01/01/2026"
    assert content["stop_date"] == "31/01/2026"
    assert content["start_time"] == "09:15"
    assert content["stop_time"] == "19:00"
    assert "uuid" in content
    assert "created_at" in content
    assert "updated_at" in content


def test_create_ignition_preset_unknown_calendar(client: TestClient) -> None:
    response = client.post(
        IGNITION_PRESETS_URL, json=ignition_preset_payload(uuid.uuid4())
    )

    assert response.status_code == 404


def test_create_ignition_preset_bad_date_format(client: TestClient) -> None:
    calendar = client.post(CALENDARS_URL, json=calendar_payload()).json()

    response = client.post(
        IGNITION_PRESETS_URL,
        json=ignition_preset_payload(calendar["uuid"], start_date="2026-01-01"),
    )

    assert response.status_code == 422


def test_create_ignition_preset_start_after_stop(client: TestClient) -> None:
    calendar = client.post(CALENDARS_URL, json=calendar_payload()).json()

    response = client.post(
        IGNITION_PRESETS_URL,
        json=ignition_preset_payload(
            calendar["uuid"], start_date="31/01/2026", stop_date="01/01/2026"
        ),
    )

    assert response.status_code == 422


def test_create_ignition_preset_overlap_rejected(client: TestClient) -> None:
    calendar = client.post(CALENDARS_URL, json=calendar_payload()).json()
    client.post(IGNITION_PRESETS_URL, json=ignition_preset_payload(calendar["uuid"]))

    response = client.post(
        IGNITION_PRESETS_URL,
        json=ignition_preset_payload(
            calendar["uuid"], start_date="15/01/2026", stop_date="15/02/2026"
        ),
    )

    assert response.status_code == 409


def test_get_ignition_preset_not_found(client: TestClient) -> None:
    response = client.get(f"{IGNITION_PRESETS_URL}{uuid.uuid4()}")

    assert response.status_code == 404


def test_list_ignition_presets(client: TestClient) -> None:
    calendar = client.post(CALENDARS_URL, json=calendar_payload()).json()
    client.post(IGNITION_PRESETS_URL, json=ignition_preset_payload(calendar["uuid"]))
    client.post(
        IGNITION_PRESETS_URL,
        json=ignition_preset_payload(
            calendar["uuid"], start_date="01/02/2026", stop_date="28/02/2026"
        ),
    )

    response = client.get(IGNITION_PRESETS_URL)

    assert response.status_code == 200
    assert response.json()["count"] == 2


def test_update_ignition_preset(client: TestClient) -> None:
    calendar = client.post(CALENDARS_URL, json=calendar_payload()).json()
    created = client.post(
        IGNITION_PRESETS_URL, json=ignition_preset_payload(calendar["uuid"])
    ).json()

    response = client.patch(
        f"{IGNITION_PRESETS_URL}{created['uuid']}", json={"name": "renamed"}
    )

    assert response.status_code == 200
    assert response.json()["name"] == "renamed"


def test_update_ignition_preset_not_found(client: TestClient) -> None:
    response = client.patch(
        f"{IGNITION_PRESETS_URL}{uuid.uuid4()}", json={"name": "renamed"}
    )

    assert response.status_code == 404


def test_update_ignition_preset_unknown_calendar(client: TestClient) -> None:
    calendar = client.post(CALENDARS_URL, json=calendar_payload()).json()
    created = client.post(
        IGNITION_PRESETS_URL, json=ignition_preset_payload(calendar["uuid"])
    ).json()

    response = client.patch(
        f"{IGNITION_PRESETS_URL}{created['uuid']}",
        json={"calendar_id": str(uuid.uuid4())},
    )

    assert response.status_code == 404


def test_update_ignition_preset_overlap_rejected(client: TestClient) -> None:
    calendar = client.post(CALENDARS_URL, json=calendar_payload()).json()
    client.post(IGNITION_PRESETS_URL, json=ignition_preset_payload(calendar["uuid"]))
    other = client.post(
        IGNITION_PRESETS_URL,
        json=ignition_preset_payload(
            calendar["uuid"], start_date="01/02/2026", stop_date="28/02/2026"
        ),
    ).json()

    response = client.patch(
        f"{IGNITION_PRESETS_URL}{other['uuid']}", json={"start_date": "15/01/2026"}
    )

    assert response.status_code == 409


def test_delete_ignition_presets_bulk(client: TestClient) -> None:
    calendar = client.post(CALENDARS_URL, json=calendar_payload()).json()
    created = client.post(
        IGNITION_PRESETS_URL, json=ignition_preset_payload(calendar["uuid"])
    ).json()

    response = client.request(
        "DELETE", IGNITION_PRESETS_URL, json={"uuids": [created["uuid"]]}
    )

    assert response.status_code == 200
    assert response.json()["message"] == "1 ignition preset(s) deleted successfully"
    assert client.get(f"{IGNITION_PRESETS_URL}{created['uuid']}").status_code == 404


def test_delete_ignition_presets_not_found(client: TestClient) -> None:
    response = client.request(
        "DELETE", IGNITION_PRESETS_URL, json={"uuids": [str(uuid.uuid4())]}
    )

    assert response.status_code == 404
