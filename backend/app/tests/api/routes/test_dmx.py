from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.services import qlc_files
from app.tests.utils import device_payload

DMX_URL = f"{settings.API_V1_STR}/dmx/"
DEVICES_URL = f"{settings.API_V1_STR}/devices/"


@pytest.fixture(autouse=True)
def _isolate_qlc_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "QLC_PROJECT_DIR", str(tmp_path / "qlc"))
    monkeypatch.setattr(qlc_files, "_push_live_reload", lambda _path: None)


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


def test_upload_requires_a_dmx_device(client: TestClient) -> None:
    client.post(DEVICES_URL, json=device_payload(handles_dmx=False))

    response = client.post(
        f"{DMX_URL}upload", files=[("files", ("show.qxw", b"<Workspace/>"))]
    )

    assert response.status_code == 400


def test_upload_404s_for_an_unprovisioned_device(client: TestClient) -> None:
    response = client.post(
        f"{DMX_URL}upload", files=[("files", ("show.qxw", b"<Workspace/>"))]
    )

    assert response.status_code == 404


def test_upload_saves_the_project_file(client: TestClient) -> None:
    client.post(DEVICES_URL, json=device_payload(handles_dmx=True))

    response = client.post(
        f"{DMX_URL}upload", files=[("files", ("show.qxw", b"<Workspace/>"))]
    )

    assert response.status_code == 200
    assert (qlc_files.project_dir() / "show.qxw").read_bytes() == b"<Workspace/>"


def test_upload_replaces_any_existing_project_file(client: TestClient) -> None:
    client.post(DEVICES_URL, json=device_payload(handles_dmx=True))
    client.post(f"{DMX_URL}upload", files=[("files", ("old.qxw", b"old"))])

    client.post(f"{DMX_URL}upload", files=[("files", ("new.qxw", b"new"))])

    remaining = sorted(qlc_files.project_dir().glob("*.qxw"))
    assert [p.name for p in remaining] == ["new.qxw"]


def test_upload_saves_a_fixture_file(client: TestClient) -> None:
    client.post(DEVICES_URL, json=device_payload(handles_dmx=True))

    response = client.post(
        f"{DMX_URL}upload", files=[("files", ("lyre.qxf", b"<FixtureDefinition/>"))]
    )

    assert response.status_code == 200
    assert (qlc_files.fixtures_dir() / "lyre.qxf").read_bytes() == b"<FixtureDefinition/>"


def test_upload_accepts_project_and_fixtures_together(client: TestClient) -> None:
    client.post(DEVICES_URL, json=device_payload(handles_dmx=True))

    response = client.post(
        f"{DMX_URL}upload",
        files=[
            ("files", ("show.qxw", b"<Workspace/>")),
            ("files", ("lyre.qxf", b"<FixtureDefinition/>")),
        ],
    )

    assert response.status_code == 200
    assert "1 project file(s), 1 fixture file(s)" in response.json()["message"]
    assert (qlc_files.project_dir() / "show.qxw").exists()
    assert (qlc_files.fixtures_dir() / "lyre.qxf").exists()


def test_upload_rejects_an_unsupported_extension(client: TestClient) -> None:
    client.post(DEVICES_URL, json=device_payload(handles_dmx=True))

    response = client.post(f"{DMX_URL}upload", files=[("files", ("show.txt", b"not qlc"))])

    assert response.status_code == 400


def test_upload_rejects_an_empty_file_list(client: TestClient) -> None:
    client.post(DEVICES_URL, json=device_payload(handles_dmx=True))

    # FastAPI's own request validation rejects a request with no "files"
    # part at all (422) before the route body ever runs -- the route's
    # own `if not files` check is unreachable for this exact case, but
    # kept as defensive documentation of the invariant.
    response = client.post(f"{DMX_URL}upload", files=[])

    assert response.status_code == 422


def test_upload_rejects_an_oversized_file(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    client.post(DEVICES_URL, json=device_payload(handles_dmx=True))
    monkeypatch.setattr(settings, "QLC_MAX_UPLOAD_BYTES", 4)

    response = client.post(f"{DMX_URL}upload", files=[("files", ("show.qxw", b"too big"))])

    assert response.status_code == 413
