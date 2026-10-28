import subprocess
from datetime import datetime

import pytest

from lora_daemon import clock


def test_sets_system_clock_and_writes_through_to_rtc(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []
    monkeypatch.setattr(
        clock.subprocess, "run", lambda args, **kwargs: calls.append(args) and None
    )

    clock.set_system_and_hardware_clock(datetime(2026, 10, 28, 9, 30, 0))

    assert calls == [
        ["date", "-s", "2026-10-28 09:30:00"],
        ["hwclock", "--systohc", "--localtime"],
    ]


def test_does_not_raise_when_date_command_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(args, **kwargs):
        if args[0] == "date":
            raise subprocess.CalledProcessError(1, args)
        raise AssertionError("hwclock should not be called when date failed")

    monkeypatch.setattr(clock.subprocess, "run", fake_run)

    clock.set_system_and_hardware_clock(datetime(2026, 10, 28, 9, 30, 0))


def test_does_not_raise_when_hwclock_command_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(args, **kwargs):
        if args[0] == "hwclock":
            raise subprocess.CalledProcessError(1, args)
        return None

    monkeypatch.setattr(clock.subprocess, "run", fake_run)

    clock.set_system_and_hardware_clock(datetime(2026, 10, 28, 9, 30, 0))


def test_does_not_raise_when_commands_are_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(args, **kwargs):
        raise FileNotFoundError(args[0])

    monkeypatch.setattr(clock.subprocess, "run", fake_run)

    clock.set_system_and_hardware_clock(datetime(2026, 10, 28, 9, 30, 0))
