from fastapi.testclient import TestClient

from app.core.config import settings
from app.services import agenda_evaluator

AGENDA_URL = f"{settings.API_V1_STR}/agenda"


def test_set_agenda_disabled_true(client: TestClient) -> None:
    assert agenda_evaluator.is_agenda_disabled() is False
    try:
        response = client.post(f"{AGENDA_URL}/disabled", json={"disabled": True})
        assert response.status_code == 200
        assert agenda_evaluator.is_agenda_disabled() is True
    finally:
        agenda_evaluator.set_agenda_disabled(False)


def test_set_agenda_disabled_false(client: TestClient) -> None:
    agenda_evaluator.set_agenda_disabled(True)
    response = client.post(f"{AGENDA_URL}/disabled", json={"disabled": False})
    assert response.status_code == 200
    assert agenda_evaluator.is_agenda_disabled() is False
