import uuid

import pytest
from sqlmodel import Session

from app import crud
from app.crud import IgnitionPresetDateRangeError, IgnitionPresetOverlapError
from app.models import (
    CalendarCreate,
    CalendarUpdate,
    IgnitionPresetCreate,
    IgnitionPresetUpdate,
)
from app.tests.utils import (
    calendar_payload,
    create_calendar,
    create_group,
    create_ignition_preset,
    ignition_preset_payload,
)


def test_create_calendar(session: Session) -> None:
    calendar_in = CalendarCreate(**calendar_payload())
    calendar = crud.create_calendar(session=session, calendar_create=calendar_in)

    assert calendar.uuid is not None
    assert calendar.label == calendar_in.label
    assert calendar.weekdays == calendar_in.weekdays
    assert calendar.created_at is not None
    assert calendar.updated_at is not None


def test_create_calendar_defaults_weekdays_to_empty(session: Session) -> None:
    payload = calendar_payload()
    del payload["weekdays"]
    calendar_in = CalendarCreate(**payload)
    calendar = crud.create_calendar(session=session, calendar_create=calendar_in)

    assert calendar.weekdays == []


def test_create_calendar_rejects_invalid_weekday() -> None:
    with pytest.raises(ValueError, match="weekdays"):
        CalendarCreate(**calendar_payload(weekdays=[0]))

    with pytest.raises(ValueError, match="weekdays"):
        CalendarCreate(**calendar_payload(weekdays=[8]))


def test_get_calendar(session: Session) -> None:
    calendar = crud.create_calendar(
        session=session, calendar_create=CalendarCreate(**calendar_payload())
    )

    fetched = crud.get_calendar(session=session, calendar_uuid=calendar.uuid)

    assert fetched is not None
    assert fetched.uuid == calendar.uuid


def test_get_calendar_not_found(session: Session) -> None:
    assert crud.get_calendar(session=session, calendar_uuid=uuid.uuid4()) is None


def test_get_calendars_pagination(session: Session) -> None:
    for _ in range(3):
        crud.create_calendar(
            session=session, calendar_create=CalendarCreate(**calendar_payload())
        )

    calendars, count = crud.get_calendars(session=session, skip=0, limit=2)

    assert count == 3
    assert len(calendars) == 2


def test_update_calendar_partial(session: Session) -> None:
    calendar = crud.create_calendar(
        session=session, calendar_create=CalendarCreate(**calendar_payload())
    )
    original_label = calendar.label
    original_updated_at = calendar.updated_at

    updated = crud.update_calendar(
        session=session,
        db_calendar=calendar,
        calendar_in=CalendarUpdate(weekdays=[6, 7]),
    )

    assert updated.weekdays == [6, 7]
    # Untouched fields keep their value: PATCH is partial.
    assert updated.label == original_label
    assert updated.updated_at >= original_updated_at


def test_update_calendar_null_weekdays_clears_it(session: Session) -> None:
    calendar = crud.create_calendar(
        session=session, calendar_create=CalendarCreate(**calendar_payload())
    )

    updated = crud.update_calendar(
        session=session,
        db_calendar=calendar,
        calendar_in=CalendarUpdate(weekdays=None),
    )

    assert updated.weekdays == []


def test_duplicate_calendar(session: Session) -> None:
    calendar = crud.create_calendar(
        session=session,
        calendar_create=CalendarCreate(**calendar_payload(label="calendar_example")),
    )
    create_ignition_preset(session, calendar_id=calendar.uuid, name="preset A")

    duplicate = crud.duplicate_calendar(session=session, db_calendar=calendar)

    assert duplicate.uuid != calendar.uuid
    assert duplicate.label == "calendar_example copy"
    assert duplicate.weekdays == calendar.weekdays
    assert len(duplicate.ignition_presets) == 1
    assert duplicate.ignition_presets[0].uuid != calendar.ignition_presets[0].uuid
    assert duplicate.ignition_presets[0].name == "preset A"


def test_duplicate_calendar_is_independent_copy(session: Session) -> None:
    calendar = crud.create_calendar(
        session=session, calendar_create=CalendarCreate(**calendar_payload())
    )
    create_ignition_preset(session, calendar_id=calendar.uuid)

    duplicate = crud.duplicate_calendar(session=session, db_calendar=calendar)
    duplicate.ignition_presets[0].name = "renamed"
    session.add(duplicate.ignition_presets[0])
    session.commit()

    session.refresh(calendar)
    assert calendar.ignition_presets[0].name != "renamed"


def test_delete_calendar(session: Session) -> None:
    calendar = crud.create_calendar(
        session=session, calendar_create=CalendarCreate(**calendar_payload())
    )

    crud.delete_calendar(session=session, db_calendar=calendar)

    assert crud.get_calendar(session=session, calendar_uuid=calendar.uuid) is None


def test_delete_calendar_cascades_to_ignition_presets(session: Session) -> None:
    calendar = crud.create_calendar(
        session=session, calendar_create=CalendarCreate(**calendar_payload())
    )
    preset = create_ignition_preset(session, calendar_id=calendar.uuid)

    crud.delete_calendar(session=session, db_calendar=calendar)

    assert crud.get_ignition_preset(session=session, ignition_preset_uuid=preset.uuid) is None


def test_calendar_groups_relationship(session: Session) -> None:
    calendar = crud.create_calendar(
        session=session, calendar_create=CalendarCreate(**calendar_payload())
    )
    create_group(session, calendar_id=calendar.uuid)

    session.refresh(calendar)

    assert len(calendar.groups) == 1


def test_create_ignition_preset(session: Session) -> None:
    calendar = create_calendar(session)
    preset_in = IgnitionPresetCreate(**ignition_preset_payload(calendar.uuid))

    preset = crud.create_ignition_preset(session=session, ignition_preset_create=preset_in)

    assert preset.uuid is not None
    assert preset.calendar_id == calendar.uuid
    assert preset.name == preset_in.name
    assert preset.start_date == "01/01/2026"
    assert preset.stop_date == "31/01/2026"
    assert preset.created_at is not None
    assert preset.updated_at is not None


def test_create_ignition_preset_rejects_start_after_stop() -> None:
    with pytest.raises(ValueError, match="start_date must not be after stop_date"):
        IgnitionPresetCreate(
            **ignition_preset_payload(
                uuid.uuid4(), start_date="31/01/2026", stop_date="01/01/2026"
            )
        )


@pytest.mark.parametrize(
    "bad_date",
    ["2026-01-01", "1/1/2026", "31/02/2026", "not-a-date"],
)
def test_create_ignition_preset_rejects_bad_date_format(bad_date: str) -> None:
    with pytest.raises(ValueError, match="date"):
        IgnitionPresetCreate(**ignition_preset_payload(uuid.uuid4(), start_date=bad_date))


@pytest.mark.parametrize("bad_time", ["9:15", "09:15:00", "25:00", "not-a-time"])
def test_create_ignition_preset_rejects_bad_time_format(bad_time: str) -> None:
    with pytest.raises(ValueError, match="time"):
        IgnitionPresetCreate(**ignition_preset_payload(uuid.uuid4(), start_time=bad_time))


def test_create_ignition_preset_overlapping_dates_rejected(session: Session) -> None:
    calendar = create_calendar(session)
    create_ignition_preset(
        session, calendar_id=calendar.uuid, start_date="01/01/2026", stop_date="31/01/2026"
    )

    overlapping = IgnitionPresetCreate(
        **ignition_preset_payload(
            calendar.uuid, start_date="15/01/2026", stop_date="15/02/2026"
        )
    )

    with pytest.raises(IgnitionPresetOverlapError):
        crud.create_ignition_preset(session=session, ignition_preset_create=overlapping)


def test_create_ignition_preset_adjacent_dates_allowed(session: Session) -> None:
    calendar = create_calendar(session)
    create_ignition_preset(
        session, calendar_id=calendar.uuid, start_date="01/01/2026", stop_date="31/01/2026"
    )

    non_overlapping = IgnitionPresetCreate(
        **ignition_preset_payload(
            calendar.uuid, start_date="01/02/2026", stop_date="28/02/2026"
        )
    )

    preset = crud.create_ignition_preset(session=session, ignition_preset_create=non_overlapping)
    assert preset.start_date == "01/02/2026"


def test_create_ignition_preset_overlap_scoped_per_calendar(session: Session) -> None:
    calendar_a = create_calendar(session)
    calendar_b = create_calendar(session)
    create_ignition_preset(
        session, calendar_id=calendar_a.uuid, start_date="01/01/2026", stop_date="31/01/2026"
    )

    same_dates_other_calendar = IgnitionPresetCreate(
        **ignition_preset_payload(
            calendar_b.uuid, start_date="01/01/2026", stop_date="31/01/2026"
        )
    )

    preset = crud.create_ignition_preset(
        session=session, ignition_preset_create=same_dates_other_calendar
    )
    assert preset.calendar_id == calendar_b.uuid


def test_create_ignition_preset_same_dates_non_overlapping_times_allowed(
    session: Session,
) -> None:
    calendar = create_calendar(session)
    create_ignition_preset(
        session,
        calendar_id=calendar.uuid,
        start_date="21/12/2026",
        stop_date="23/12/2026",
        start_time="15:30",
        stop_time="17:00",
    )

    non_overlapping = IgnitionPresetCreate(
        **ignition_preset_payload(
            calendar.uuid,
            start_date="21/12/2026",
            stop_date="23/12/2026",
            start_time="18:00",
            stop_time="22:00",
        )
    )

    preset = crud.create_ignition_preset(session=session, ignition_preset_create=non_overlapping)
    assert preset.start_time == "18:00"


def test_create_ignition_preset_same_dates_overlapping_times_rejected(
    session: Session,
) -> None:
    calendar = create_calendar(session)
    create_ignition_preset(
        session,
        calendar_id=calendar.uuid,
        start_date="21/12/2026",
        stop_date="23/12/2026",
        start_time="15:30",
        stop_time="17:00",
    )

    overlapping = IgnitionPresetCreate(
        **ignition_preset_payload(
            calendar.uuid,
            start_date="21/12/2026",
            stop_date="23/12/2026",
            start_time="16:30",
            stop_time="22:00",
        )
    )

    with pytest.raises(IgnitionPresetOverlapError):
        crud.create_ignition_preset(session=session, ignition_preset_create=overlapping)


def test_create_ignition_preset_back_to_back_times_allowed(session: Session) -> None:
    calendar = create_calendar(session)
    create_ignition_preset(
        session,
        calendar_id=calendar.uuid,
        start_date="21/12/2026",
        stop_date="23/12/2026",
        start_time="15:30",
        stop_time="17:00",
    )

    back_to_back = IgnitionPresetCreate(
        **ignition_preset_payload(
            calendar.uuid,
            start_date="21/12/2026",
            stop_date="23/12/2026",
            start_time="17:00",
            stop_time="18:00",
        )
    )

    preset = crud.create_ignition_preset(session=session, ignition_preset_create=back_to_back)
    assert preset.start_time == "17:00"


def test_update_ignition_preset(session: Session) -> None:
    calendar = create_calendar(session)
    preset = create_ignition_preset(session, calendar_id=calendar.uuid)

    updated = crud.update_ignition_preset(
        session=session,
        db_ignition_preset=preset,
        ignition_preset_in=IgnitionPresetUpdate(name="renamed"),
    )

    assert updated.name == "renamed"
    assert updated.start_date == preset.start_date


def test_update_ignition_preset_rejects_start_after_stop(session: Session) -> None:
    calendar = create_calendar(session)
    preset = create_ignition_preset(
        session, calendar_id=calendar.uuid, start_date="01/01/2026", stop_date="31/01/2026"
    )

    with pytest.raises(IgnitionPresetDateRangeError):
        crud.update_ignition_preset(
            session=session,
            db_ignition_preset=preset,
            ignition_preset_in=IgnitionPresetUpdate(start_date="15/02/2026"),
        )


def test_update_ignition_preset_overlap_excludes_self(session: Session) -> None:
    calendar = create_calendar(session)
    preset = create_ignition_preset(
        session, calendar_id=calendar.uuid, start_date="01/01/2026", stop_date="31/01/2026"
    )

    # Updating a preset's own dates to overlap with itself must not raise.
    updated = crud.update_ignition_preset(
        session=session,
        db_ignition_preset=preset,
        ignition_preset_in=IgnitionPresetUpdate(stop_date="28/02/2026"),
    )
    assert updated.stop_date == "28/02/2026"


def test_update_ignition_preset_overlap_with_other_preset_rejected(session: Session) -> None:
    calendar = create_calendar(session)
    create_ignition_preset(
        session, calendar_id=calendar.uuid, start_date="01/01/2026", stop_date="31/01/2026"
    )
    other = create_ignition_preset(
        session, calendar_id=calendar.uuid, start_date="01/02/2026", stop_date="28/02/2026"
    )

    with pytest.raises(IgnitionPresetOverlapError):
        crud.update_ignition_preset(
            session=session,
            db_ignition_preset=other,
            ignition_preset_in=IgnitionPresetUpdate(start_date="15/01/2026"),
        )


def test_delete_ignition_preset(session: Session) -> None:
    calendar = create_calendar(session)
    preset = create_ignition_preset(session, calendar_id=calendar.uuid)

    crud.delete_ignition_preset(session=session, db_ignition_preset=preset)

    assert crud.get_ignition_preset(session=session, ignition_preset_uuid=preset.uuid) is None
