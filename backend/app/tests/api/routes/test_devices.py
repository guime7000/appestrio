import uuid

import pytest
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


def test_sync_config_not_found(client: TestClient) -> None:
    response = client.post(f"{DEVICES_URL}sync-config", json={"device_ids": ["nosuch"]})

    assert response.status_code == 404


def test_sync_config_requires_at_least_one_device_id(client: TestClient) -> None:
    response = client.post(f"{DEVICES_URL}sync-config", json={"device_ids": []})

    assert response.status_code == 422


def test_sync_config_skips_already_synced_devices(
    client: TestClient, session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app import crud
    from app.services import lora_daemon_client

    created = client.post(DEVICES_URL, json=device_payload(device_number=1)).json()
    device = crud.get_device_by_device_id(session=session, device_id=created["device_id"])
    assert device is not None
    crud.mark_device_synced(session=session, device=device, version=device.config_version)

    def _fail(*_args: object, **_kwargs: object) -> bool:
        raise AssertionError("should not push an already-synced device")

    monkeypatch.setattr(lora_daemon_client, "sync_device_config_and_wait", _fail)

    response = client.post(
        f"{DEVICES_URL}sync-config", json={"device_ids": [created["device_id"]]}
    )

    assert response.status_code == 200
    assert "Aucune configuration en attente" in response.json()["message"]


def test_sync_config_marks_lumestrio_synced_once_confirmed(
    client: TestClient, session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app import crud
    from app.services import lora_daemon_client

    created = client.post(
        DEVICES_URL, json=device_payload(device_type="lumestrio", device_number=2)
    ).json()
    device_id = created["device_id"]

    monkeypatch.setattr(
        lora_daemon_client, "sync_device_config_and_wait", lambda _device_id, **_kw: True
    )
    monkeypatch.setattr(
        lora_daemon_client,
        "check_config_sync",
        lambda _device_ids, **_kw: {"results": {device_id: True}},
    )

    response = client.post(f"{DEVICES_URL}sync-config", json={"device_ids": [device_id]})

    assert response.status_code == 200
    assert "1/1 appareil(s) mis à jour" in response.json()["message"]
    device = crud.get_device_by_device_id(session=session, device_id=device_id)
    assert device is not None
    assert device.synced_version == device.config_version


def test_sync_config_does_not_mark_lumestrio_synced_without_real_confirmation(
    client: TestClient, session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app import crud
    from app.services import lora_daemon_client

    created = client.post(
        DEVICES_URL, json=device_payload(device_type="lumestrio", device_number=3)
    ).json()
    device_id = created["device_id"]

    monkeypatch.setattr(
        lora_daemon_client, "sync_device_config_and_wait", lambda _device_id, **_kw: True
    )
    monkeypatch.setattr(
        lora_daemon_client, "check_config_sync", lambda _device_ids, **_kw: {"results": {}}
    )

    response = client.post(f"{DEVICES_URL}sync-config", json={"device_ids": [device_id]})

    assert response.status_code == 200
    assert "0/1 appareil(s) mis à jour" in response.json()["message"]
    assert device_id in response.json()["message"]
    device = crud.get_device_by_device_id(session=session, device_id=device_id)
    assert device is not None
    assert device.synced_version != device.config_version


def test_sync_config_marks_relaystrio_synced_on_delivery_alone(
    client: TestClient, session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app import crud
    from app.services import lora_daemon_client

    created = client.post(
        DEVICES_URL, json=device_payload(device_type="relaystrio", device_number=4)
    ).json()
    device_id = created["device_id"]

    monkeypatch.setattr(
        lora_daemon_client, "sync_device_config_and_wait", lambda _device_id, **_kw: True
    )

    def _fail(*_args: object, **_kwargs: object) -> dict:
        raise AssertionError("relaystrio has no config_version to confirm over LoRa")

    monkeypatch.setattr(lora_daemon_client, "check_config_sync", _fail)

    response = client.post(f"{DEVICES_URL}sync-config", json={"device_ids": [device_id]})

    assert response.status_code == 200
    assert "1/1 appareil(s) mis à jour" in response.json()["message"]
    device = crud.get_device_by_device_id(session=session, device_id=device_id)
    assert device is not None
    assert device.synced_version == device.config_version


def test_sync_config_reports_failure_when_push_fails(
    client: TestClient, session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app import crud
    from app.services import lora_daemon_client

    created = client.post(DEVICES_URL, json=device_payload(device_number=5)).json()
    device_id = created["device_id"]

    monkeypatch.setattr(
        lora_daemon_client, "sync_device_config_and_wait", lambda _device_id, **_kw: False
    )

    response = client.post(f"{DEVICES_URL}sync-config", json={"device_ids": [device_id]})

    assert response.status_code == 200
    assert "0/1 appareil(s) mis à jour" in response.json()["message"]
    device = crud.get_device_by_device_id(session=session, device_id=device_id)
    assert device is not None
    assert device.synced_version != device.config_version


def test_sync_config_survives_unreachable_lora_daemon(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services import lora_daemon_client
    from app.services.lora_daemon_client import LoraDaemonError

    created = client.post(DEVICES_URL, json=device_payload(device_number=6)).json()

    def _raise(*_args: object, **_kwargs: object) -> bool:
        raise LoraDaemonError("unreachable")

    monkeypatch.setattr(lora_daemon_client, "sync_device_config_and_wait", _raise)

    response = client.post(
        f"{DEVICES_URL}sync-config", json={"device_ids": [created["device_id"]]}
    )

    assert response.status_code == 200
    assert "0/1 appareil(s) mis à jour" in response.json()["message"]


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


def test_update_device_ignores_device_type(client: TestClient) -> None:
    """device_type is immutable -- it's encoded into device_id, so a PATCH
    can't be allowed to desync them (see DeviceUpdate's comment).
    """
    created = client.post(
        DEVICES_URL, json=device_payload(device_type="lumestrio", device_number=1)
    ).json()

    response = client.patch(
        f"{DEVICES_URL}{created['device_id']}", json={"device_type": "relaystrio"}
    )

    assert response.status_code == 200
    assert response.json()["device_type"] == "lumestrio"


def test_update_device_not_found(client: TestClient) -> None:
    response = client.patch(
        f"{DEVICES_URL}nosuchdevice", json={"audiofile": "new_audio.mp3"}
    )

    assert response.status_code == 404


def test_update_device_active_triggers_remote_activate(
    client: TestClient, session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app import crud
    from app.services import lora_daemon_client

    calls = []
    monkeypatch.setattr(
        lora_daemon_client,
        "send_activate",
        lambda active, addresses=None, **kwargs: calls.append((active, addresses)),
    )
    created = client.post(
        DEVICES_URL, json=device_payload(device_type="lumestrio", device_number=3)
    ).json()
    db_device = crud.get_device_by_device_id(session=session, device_id=created["device_id"])
    crud.mark_device_synced(session=session, device=db_device, version=db_device.config_version)

    response = client.patch(f"{DEVICES_URL}{created['device_id']}", json={"active": False})

    assert response.status_code == 200
    assert response.json()["active"] is False
    # lumestrio address = device_number + 32 * LORA_TYPE_INDEX[lumestrio] (1)
    assert calls == [(False, [35])]
    assert created["device_id"] not in client.get(f"{DEVICES_URL}pending-sync").json()[
        "device_ids"
    ]


def test_update_device_active_does_not_bump_config_version(
    client: TestClient, session: Session
) -> None:
    from app import crud

    created = client.post(DEVICES_URL, json=device_payload()).json()
    db_device = crud.get_device_by_device_id(session=session, device_id=created["device_id"])
    crud.mark_device_synced(session=session, device=db_device, version=db_device.config_version)

    client.patch(f"{DEVICES_URL}{created['device_id']}", json={"active": False})

    pending = client.get(f"{DEVICES_URL}pending-sync").json()["device_ids"]
    assert created["device_id"] not in pending


def test_update_device_active_alongside_other_field_bumps_config_version(
    client: TestClient, session: Session
) -> None:
    from app import crud

    created = client.post(DEVICES_URL, json=device_payload()).json()
    db_device = crud.get_device_by_device_id(session=session, device_id=created["device_id"])
    crud.mark_device_synced(session=session, device=db_device, version=db_device.config_version)

    response = client.patch(
        f"{DEVICES_URL}{created['device_id']}",
        json={"active": False, "audiofile": "new_audio.mp3"},
    )

    assert response.status_code == 200
    pending = client.get(f"{DEVICES_URL}pending-sync").json()["device_ids"]
    assert created["device_id"] in pending


def test_update_device_active_survives_unreachable_lora_daemon(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services import lora_daemon_client
    from app.services.lora_daemon_client import LoraDaemonError

    def _raise(*_args, **_kwargs):
        raise LoraDaemonError("unreachable")

    monkeypatch.setattr(lora_daemon_client, "send_activate", _raise)
    created = client.post(DEVICES_URL, json=device_payload()).json()

    response = client.patch(f"{DEVICES_URL}{created['device_id']}", json={"active": False})

    assert response.status_code == 200
    assert response.json()["active"] is False


def test_update_device_without_active_does_not_call_remote_activate(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services import lora_daemon_client

    calls = []
    monkeypatch.setattr(
        lora_daemon_client,
        "send_activate",
        lambda active, addresses=None, **kwargs: calls.append((active, addresses)),
    )
    created = client.post(DEVICES_URL, json=device_payload()).json()

    client.patch(f"{DEVICES_URL}{created['device_id']}", json={"audiofile": "new_audio.mp3"})

    assert calls == []


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


def test_activate_device_calls_apply_active_state(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Not caplog: alembic's env.py calls logging.config.fileConfig() during
    # this fixture's own lifespan-triggered migration run, which disables
    # every logger that already existed and isn't named in alembic.ini --
    # including this module's, before any test body ever runs. Asserting
    # the real call (and its arguments) is also a stronger check than
    # matching log text would have been.
    calls = []
    monkeypatch.setattr(
        "app.api.routes.devices.apply_active_state",
        lambda **kwargs: calls.append(kwargs),
    )
    created = client.post(
        DEVICES_URL, json=device_payload(handles_audio=True, audiofile="track.mp3")
    ).json()

    response = client.post(f"{DEVICES_URL}{created['device_id']}/activate", json={"active": True})

    assert response.status_code == 200
    assert response.json()["message"] == f"activation applied for {created['device_id']}"
    assert calls == [
        {
            "device_id": created["device_id"],
            "active": True,
            "handles_audio": True,
            "handles_dmx": False,
            "audiofile": "track.mp3",
        }
    ]


def test_activate_device_not_found(client: TestClient) -> None:
    response = client.post(f"{DEVICES_URL}nosuchdevice/activate", json={"active": True})

    assert response.status_code == 404
