import pytest

from app.core.identity import resolve_own_device_identity
from app.models import DeviceType


def test_resolves_lumestrio_hostname() -> None:
    assert resolve_own_device_identity("lumestrio3") == (DeviceType.LUMESTRIO, 3)


def test_resolves_relaystrio_hostname() -> None:
    assert resolve_own_device_identity("relaystrio12") == (DeviceType.RELAYSTRIO, 12)


def test_strips_domain_suffix() -> None:
    assert resolve_own_device_identity("lumestrio3.local") == (DeviceType.LUMESTRIO, 3)


def test_returns_none_for_non_matching_hostname() -> None:
    assert resolve_own_device_identity("raspberrypi") is None


def test_returns_none_for_prefix_without_digits() -> None:
    assert resolve_own_device_identity("lumestrio") is None


def test_returns_none_for_non_digit_suffix() -> None:
    assert resolve_own_device_identity("lumestrioX") is None


def test_uses_lora_hostname_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LORA_HOSTNAME", "lumestrio7")
    assert resolve_own_device_identity() == (DeviceType.LUMESTRIO, 7)


def test_falls_back_to_socket_gethostname(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LORA_HOSTNAME", raising=False)
    monkeypatch.setattr("socket.gethostname", lambda: "lumestrio9")
    assert resolve_own_device_identity() == (DeviceType.LUMESTRIO, 9)
