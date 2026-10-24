"""Builds `relaystrio`'s frozen `Agenda` JSON (`SchedulerAPI.h`, see
`Legacy/relaystrio/SchedulerAPI.h` for the exact schema this must match
byte-for-byte on field names) from the native `Calendar`/`IgnitionPreset`
model. The two schemas don't map 1:1 -- see Lora_Rewrite_Plan.md's item 4
section for the full design discussion -- so this is a real conversion,
not a field-for-field translation.

Key structural mismatch this works around: a `relaystrio` `AgendaException`
whose date range matches today **fully replaces** that day's schedule --
`defaultWeek` isn't consulted at all that day (`Agenda::isActiveForLocalTime`
returns on the first matching exception). The native model instead treats
every `IgnitionPreset` as an independent, OR-combined window -- any
preset whose date/weekday/time all match turns the device on, regardless
of what else does too. To keep both ends behaviorally equivalent, an
exception's `hourRangeList` must include not just its own preset's window
but also whatever the recurring/`defaultWeek` baseline would have
contributed that day -- otherwise a short override would silently
swallow an unrelated standing schedule on the same date.

Presets are classified "recurring" (-> `defaultWeek`, cheap: one entry
per weekday regardless of how long the preset's date range is) vs
"temporary override" (-> `agendaExceptionList`, which can require
day-by-day expansion since `relaystrio` has no concept of "only these
weekdays within this date range") by comparing each preset's own
date-range length against `LoraSettings.relaystrio_recurring_threshold_days`
-- a master-side-only setting, never transmitted to any device.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from .db import CalendarRow, IgnitionPresetRow

_DATE_FORMAT = "%d/%m/%Y"
# Index 0 = Monday, matching Calendar.weekdays' own ISO weekday numbering
# (1=Monday..7=Sunday) via `_weekday_name(iso_weekday)` below -- same
# order relaystrio's own `dayNames()` uses.
_WEEKDAY_NAMES = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]


def _parse_date(value: str) -> datetime:
    return datetime.strptime(value, _DATE_FORMAT)


def _format_date(value: datetime) -> str:
    return value.strftime(_DATE_FORMAT)


def _weekday_name(iso_weekday: int) -> str:
    return _WEEKDAY_NAMES[iso_weekday - 1]


@dataclass(frozen=True)
class _HourRange:
    start: str
    end: str

    def to_dict(self) -> dict:
        return {"start": self.start, "end": self.end}


def _preset_span_days(preset: IgnitionPresetRow) -> int:
    return (_parse_date(preset.stop_date) - _parse_date(preset.start_date)).days + 1


def _is_recurring(preset: IgnitionPresetRow, threshold_days: int) -> bool:
    return _preset_span_days(preset) >= threshold_days


def _dedupe(ranges: list[_HourRange]) -> list[_HourRange]:
    seen: list[_HourRange] = []
    for r in ranges:
        if r not in seen:
            seen.append(r)
    return seen


def _empty_agenda(name: str) -> dict:
    return {
        "name": name,
        "defaultWeek": {
            "defaultDay": {"dayName": "default", "hourRangeList": []},
            "exceptions": [],
        },
        "agendaExceptionList": [],
    }


def build_relaystrio_agenda(
    calendar: CalendarRow | None,
    *,
    recurring_threshold_days: int,
    name: str = "default",
) -> dict:
    """Returns a plain dict ready for `json.dumps`, matching relaystrio's
    exact `Agenda`/`WeekType`/`DayType`/`HourRange`/`AgendaException`
    field names. `calendar=None` (no calendar assigned to this device's
    group) yields an always-off agenda -- `defaultDay`'s empty
    `hourRangeList` means "never active", matching a `lumestrio` with no
    calendar never being scheduled on either.
    """
    if calendar is None:
        return _empty_agenda(name)

    recurring = [p for p in calendar.presets if _is_recurring(p, recurring_threshold_days)]
    temporary = [p for p in calendar.presets if not _is_recurring(p, recurring_threshold_days)]

    recurring_by_weekday: dict[int, list[_HourRange]] = {}
    for preset in recurring:
        hour_range = _HourRange(preset.start_time, preset.stop_time)
        for weekday in calendar.weekdays:
            recurring_by_weekday.setdefault(weekday, []).append(hour_range)

    default_week = {
        "defaultDay": {"dayName": "default", "hourRangeList": []},
        "exceptions": [
            {
                "dayName": _weekday_name(weekday),
                "hourRangeList": [hr.to_dict() for hr in _dedupe(ranges)],
            }
            for weekday, ranges in sorted(recurring_by_weekday.items())
        ],
    }

    return {
        "name": name,
        "defaultWeek": default_week,
        "agendaExceptionList": _build_exception_list(
            temporary, calendar.weekdays, recurring_by_weekday, name
        ),
    }


def _build_exception_list(
    temporary: list[IgnitionPresetRow],
    weekdays: list[int],
    recurring_by_weekday: dict[int, list[_HourRange]],
    name: str,
) -> list[dict]:
    # date -> merged hour ranges: the temporary preset(s) covering that
    # exact date, plus whatever the recurring baseline contributes for
    # that weekday -- an exception fully replaces the day in relaystrio's
    # firmware, so anything not folded in here would be silently lost.
    by_date: dict[datetime, list[_HourRange]] = {}
    for preset in temporary:
        hour_range = _HourRange(preset.start_time, preset.stop_time)
        day = _parse_date(preset.start_date)
        stop = _parse_date(preset.stop_date)
        while day <= stop:
            if day.isoweekday() in weekdays:
                ranges = by_date.setdefault(
                    day, list(recurring_by_weekday.get(day.isoweekday(), []))
                )
                if hour_range not in ranges:
                    ranges.append(hour_range)
            day += timedelta(days=1)

    if not by_date:
        return []

    # Consolidate contiguous dates sharing the exact same hour-range set
    # into one exception instead of one per day -- real airtime cost in a
    # 59-byte-capped FILE_MSG otherwise (e.g. a one-week holiday override
    # becomes 1 exception, not 7).
    sorted_dates = sorted(by_date)
    exceptions: list[dict] = []

    group_start = sorted_dates[0]
    group_end = sorted_dates[0]
    group_ranges = by_date[sorted_dates[0]]

    def _group_key(ranges: list[_HourRange]) -> tuple:
        return tuple(sorted((r.start, r.end) for r in ranges))

    group_key = _group_key(group_ranges)

    def _flush() -> None:
        exceptions.append(
            {
                "name": name,
                "dates": {"start": _format_date(group_start), "end": _format_date(group_end)},
                "dayValue": {
                    "dayName": "exception",
                    "hourRangeList": [
                        hr.to_dict() for hr in sorted(group_ranges, key=lambda r: r.start)
                    ],
                },
            }
        )

    for current_date in sorted_dates[1:]:
        ranges = by_date[current_date]
        key = _group_key(ranges)
        if (current_date - group_end).days == 1 and key == group_key:
            group_end = current_date
            continue
        _flush()
        group_start = current_date
        group_end = current_date
        group_ranges = ranges
        group_key = key

    _flush()
    return exceptions
