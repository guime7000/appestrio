from lora_daemon.db import CalendarRow, IgnitionPresetRow
from lora_daemon.relaystrio_agenda import build_relaystrio_agenda

THRESHOLD = 60


def _preset(**overrides) -> IgnitionPresetRow:
    base = {
        "uuid": "preset-1",
        "name": "default",
        "description": None,
        "start_date": "01/01/2026",
        "stop_date": "31/01/2026",
        "start_time": "09:00",
        "stop_time": "18:00",
    }
    base.update(overrides)
    return IgnitionPresetRow(**base)


def _calendar(**overrides) -> CalendarRow:
    base = {
        "uuid": "cal-1",
        "label": "Default",
        "weekdays": [1, 2, 3, 4, 5, 6, 7],
        "presets": [],
    }
    base.update(overrides)
    return CalendarRow(**base)


def test_no_calendar_yields_always_off_agenda() -> None:
    agenda = build_relaystrio_agenda(None, recurring_threshold_days=THRESHOLD)

    assert agenda == {
        "name": "default",
        "defaultWeek": {
            "defaultDay": {"dayName": "default", "hourRangeList": []},
            "exceptions": [],
        },
        "agendaExceptionList": [],
    }


def test_recurring_preset_full_week_goes_to_default_week() -> None:
    preset = _preset(start_date="01/01/2026", stop_date="31/12/2026")
    calendar = _calendar(presets=[preset])

    agenda = build_relaystrio_agenda(calendar, recurring_threshold_days=THRESHOLD)

    assert agenda["agendaExceptionList"] == []
    assert len(agenda["defaultWeek"]["exceptions"]) == 7
    for day_entry in agenda["defaultWeek"]["exceptions"]:
        assert day_entry["hourRangeList"] == [{"start": "09:00", "end": "18:00"}]


def test_recurring_preset_restricted_weekdays_only_fills_those_days() -> None:
    preset = _preset(start_date="01/01/2026", stop_date="31/12/2026")
    calendar = _calendar(weekdays=[1, 2, 3, 4, 5], presets=[preset])  # Mon-Fri

    agenda = build_relaystrio_agenda(calendar, recurring_threshold_days=THRESHOLD)

    day_names = {e["dayName"] for e in agenda["defaultWeek"]["exceptions"]}
    assert day_names == {"lundi", "mardi", "mercredi", "jeudi", "vendredi"}
    # Weekends get no entry at all -- they fall back to defaultDay (off).
    assert "samedi" not in day_names
    assert "dimanche" not in day_names


def test_recurring_presets_dedupe_identical_hour_ranges_per_weekday() -> None:
    preset_a = _preset(uuid="a", start_date="01/01/2026", stop_date="31/12/2026")
    preset_b = _preset(uuid="b", start_date="01/06/2026", stop_date="31/12/2027")
    calendar = _calendar(weekdays=[1], presets=[preset_a, preset_b])

    agenda = build_relaystrio_agenda(calendar, recurring_threshold_days=THRESHOLD)

    [monday] = agenda["defaultWeek"]["exceptions"]
    assert monday["dayName"] == "lundi"
    assert monday["hourRangeList"] == [{"start": "09:00", "end": "18:00"}]


def test_temporary_preset_full_week_becomes_one_exception() -> None:
    preset = _preset(
        start_date="05/01/2026", stop_date="09/01/2026", start_time="10:00", stop_time="12:00"
    )
    calendar = _calendar(presets=[preset])  # 2026-01-05..09 is Mon..Fri

    agenda = build_relaystrio_agenda(calendar, recurring_threshold_days=THRESHOLD)

    assert agenda["defaultWeek"]["exceptions"] == []
    [exception] = agenda["agendaExceptionList"]
    assert exception["dates"] == {"start": "05/01/2026", "end": "09/01/2026"}
    assert exception["dayValue"]["hourRangeList"] == [{"start": "10:00", "end": "12:00"}]


def test_temporary_preset_restricted_weekdays_skips_non_matching_days() -> None:
    # 2026-01-05 (Mon) .. 2026-01-11 (Sun), restricted to Mon/Wed/Fri.
    preset = _preset(
        start_date="05/01/2026", stop_date="11/01/2026", start_time="10:00", stop_time="12:00"
    )
    calendar = _calendar(weekdays=[1, 3, 5], presets=[preset])

    agenda = build_relaystrio_agenda(calendar, recurring_threshold_days=THRESHOLD)

    exceptions = agenda["agendaExceptionList"]
    covered_dates = {e["dates"]["start"] for e in exceptions} | {
        e["dates"]["end"] for e in exceptions
    }
    # Monday 05/01, Wednesday 07/01, Friday 09/01 -- each isolated (not
    # contiguous with each other), so three separate single-day exceptions.
    assert len(exceptions) == 3
    for exception in exceptions:
        assert exception["dates"]["start"] == exception["dates"]["end"]
    assert covered_dates == {"05/01/2026", "07/01/2026", "09/01/2026"}


def test_temporary_exception_merges_in_recurring_baseline_for_same_day() -> None:
    """The critical correctness case: relaystrio's exception REPLACES the
    whole day, so a short override must carry the recurring baseline's
    hour range along with its own, or the standing schedule would be
    silently lost for that one date.
    """
    recurring = _preset(
        uuid="standing",
        start_date="01/01/2026",
        stop_date="31/12/2026",
        start_time="18:00",
        stop_time="23:00",
    )
    override = _preset(
        uuid="special",
        start_date="05/01/2026",
        stop_date="05/01/2026",
        start_time="09:00",
        stop_time="10:00",
    )
    calendar = _calendar(presets=[recurring, override])

    agenda = build_relaystrio_agenda(calendar, recurring_threshold_days=THRESHOLD)

    [exception] = agenda["agendaExceptionList"]
    assert exception["dates"] == {"start": "05/01/2026", "end": "05/01/2026"}
    assert sorted(exception["dayValue"]["hourRangeList"], key=lambda r: r["start"]) == [
        {"start": "09:00", "end": "10:00"},
        {"start": "18:00", "end": "23:00"},
    ]
    # And the recurring baseline still covers every other day via
    # defaultWeek, untouched by the one-day override.
    assert len(agenda["defaultWeek"]["exceptions"]) == 7


def test_contiguous_temporary_exceptions_with_different_ranges_dont_merge() -> None:
    preset_a = _preset(
        uuid="a", start_date="05/01/2026", stop_date="06/01/2026", start_time="09:00", stop_time="10:00"
    )
    preset_b = _preset(
        uuid="b", start_date="07/01/2026", stop_date="08/01/2026", start_time="14:00", stop_time="15:00"
    )
    calendar = _calendar(presets=[preset_a, preset_b])

    agenda = build_relaystrio_agenda(calendar, recurring_threshold_days=THRESHOLD)

    exceptions = agenda["agendaExceptionList"]
    assert len(exceptions) == 2
    assert exceptions[0]["dates"] == {"start": "05/01/2026", "end": "06/01/2026"}
    assert exceptions[1]["dates"] == {"start": "07/01/2026", "end": "08/01/2026"}
