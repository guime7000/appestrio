import pytest
from fastapi.testclient import TestClient

from app.core.config import settings

WHOAMI_URL = f"{settings.API_V1_STR}/whoami"


def test_whoami_defaults_to_not_master(client: TestClient) -> None:
    response = client.get(WHOAMI_URL)

    assert response.status_code == 200
    assert response.json() == {"is_master": False}


def test_whoami_reflects_is_master_setting(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "IS_MASTER", True)

    response = client.get(WHOAMI_URL)

    assert response.status_code == 200
    assert response.json() == {"is_master": True}
