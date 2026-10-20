import json

import httpx
import pytest

from app.services import lora_daemon_client as client_module


def _mock_client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler), base_url="http://lora-daemon:8765")


def test_trigger_clock_sync_calls_expected_route() -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["path"] = request.url.path
        return httpx.Response(200, json={"sent": True})

    result = client_module.trigger_clock_sync(client=_mock_client(handler))

    assert seen == {"method": "POST", "path": "/clock-sync"}
    assert result == {"sent": True}


def test_trigger_sync_config_targets_device() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/devices/lumestrio3/sync-config"
        return httpx.Response(202, json={"started": True, "device_id": "lumestrio3"})

    result = client_module.trigger_sync_config("lumestrio3", client=_mock_client(handler))

    assert result == {"started": True, "device_id": "lumestrio3"}


def test_send_activate_sends_body() -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = request.content
        return httpx.Response(200, json={"active": True, "addresses": [3]})

    result = client_module.send_activate(True, [3], client=_mock_client(handler))

    assert json.loads(seen["body"]) == {"active": True, "addresses": [3]}
    assert result == {"active": True, "addresses": [3]}


def test_request_raises_lora_daemon_error_on_connection_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    with pytest.raises(client_module.LoraDaemonError):
        client_module.trigger_clock_sync(client=_mock_client(handler))


def test_request_raises_lora_daemon_error_on_http_error_status() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "unknown device_id"})

    with pytest.raises(client_module.LoraDaemonError):
        client_module.trigger_sync_config("nosuchdevice", client=_mock_client(handler))
