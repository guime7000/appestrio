import json

from lora_daemon.config_payload import build_device_config_payload
from lora_daemon.db import CalendarRow, DeviceConfigRow, IgnitionPresetRow


def _row(**overrides) -> DeviceConfigRow:
    base = {
        "device_id": "lumestrio3",
        "device_name": "Lumestrio 3",
        "device_type": "lumestrio",
        "active": True,
        "is_master": False,
        "handles_audio": True,
        "handles_dmx": False,
        "audiofile": "song.mp3",
        "ip": "10.0.0.5",
        "master_ip": "10.0.0.1",
        "config_version": 7,
        "group_label": "Jardin",
        "calendar": None,
    }
    base.update(overrides)
    return DeviceConfigRow(**base)


def test_payload_without_calendar() -> None:
    payload = build_device_config_payload(_row())

    assert payload.config_version == 7
    assert payload.device_name == "Lumestrio 3"
    assert payload.handles_audio is True
    assert payload.group == "Jardin"
    assert payload.calendar is None


def test_payload_with_calendar_and_presets() -> None:
    calendar = CalendarRow(
        uuid="cal-1",
        label="Été",
        weekdays=[6, 7],
        presets=[
            IgnitionPresetRow(
                uuid="preset-1",
                name="Soirée",
                description=None,
                start_date="01/06/2026",
                stop_date="31/08/2026",
                start_time="20:00",
                stop_time="23:30",
            )
        ],
    )
    payload = build_device_config_payload(_row(calendar=calendar))

    assert payload.calendar is not None
    assert payload.calendar.label == "Été"
    assert payload.calendar.weekdays == [6, 7]
    assert len(payload.calendar.ignition_presets) == 1
    assert payload.calendar.ignition_presets[0].name == "Soirée"


def test_payload_serializes_to_json_bytes() -> None:
    payload = build_device_config_payload(_row())

    encoded = payload.to_json_bytes()
    decoded = json.loads(encoded)

    assert decoded["device_name"] == "Lumestrio 3"
    assert decoded["config_version"] == 7
    assert decoded["calendar"] is None


def test_payload_json_round_trips_nested_calendar() -> None:
    calendar = CalendarRow(uuid="cal-1", label="Été", weekdays=[6, 7], presets=[])
    payload = build_device_config_payload(_row(calendar=calendar))

    decoded = json.loads(payload.to_json_bytes())

    assert decoded["calendar"]["label"] == "Été"
    assert decoded["calendar"]["weekdays"] == [6, 7]
    assert decoded["calendar"]["ignition_presets"] == []
