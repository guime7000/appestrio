import pytest

from app.core.config import settings
from app.services import relay


class _FakeDevice:
    def __init__(self) -> None:
        self.state: bool | None = None
        self.closed = False

    def on(self) -> None:
        self.state = True

    def off(self) -> None:
        self.state = False

    def close(self) -> None:
        self.closed = True


@pytest.fixture(autouse=True)
def _reset_relay_state() -> None:
    relay._device = None
    relay._device_pin = None


def test_activate_true_turns_the_device_on(monkeypatch: pytest.MonkeyPatch) -> None:
    device = _FakeDevice()
    monkeypatch.setattr(relay, "_make_device", lambda _pin: device)

    relay.activate(True)

    assert device.state is True


def test_activate_false_turns_the_device_off(monkeypatch: pytest.MonkeyPatch) -> None:
    device = _FakeDevice()
    monkeypatch.setattr(relay, "_make_device", lambda _pin: device)

    relay.activate(True)
    relay.activate(False)

    assert device.state is False


def test_activate_reuses_the_same_device_across_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    created: list[_FakeDevice] = []

    def _make(_pin: int) -> _FakeDevice:
        device = _FakeDevice()
        created.append(device)
        return device

    monkeypatch.setattr(relay, "_make_device", _make)

    relay.activate(True)
    relay.activate(False)

    assert len(created) == 1


def test_activate_recreates_the_device_when_pin_setting_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created: list[_FakeDevice] = []

    def _make(_pin: int) -> _FakeDevice:
        device = _FakeDevice()
        created.append(device)
        return device

    monkeypatch.setattr(relay, "_make_device", _make)

    relay.activate(True)
    monkeypatch.setattr(settings, "AUDIO_RELAY_GPIO_PIN", 99)
    relay.activate(True)

    assert len(created) == 2
    assert created[0].closed is True


def test_activate_survives_a_missing_gpio_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(_pin: int) -> _FakeDevice:
        raise RuntimeError("no GPIO backend available")

    monkeypatch.setattr(relay, "_make_device", _raise)

    relay.activate(True)  # must not raise
