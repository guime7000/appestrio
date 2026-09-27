from sqlmodel import Session

from app import crud
from app.models import LoraSettingsUpdate


def test_get_lora_settings_creates_singleton_with_default_matching_relaystrio(
    session: Session,
) -> None:
    settings = crud.get_lora_settings(session=session)

    assert settings.id == 1
    assert settings.is_active is False
    # channel=0/speed=2 match relaystrio's fixed-in-firmware E32 config,
    # not legacy's own software default (channel=40/speed=3) -- see
    # app/models/lora_settings.py's comment for why.
    assert settings.channel == 0
    assert settings.speed == 2
    assert settings.fec is True
    assert settings.ping_interval_s == 5
    assert settings.clock_interval_s == 60


def test_get_lora_settings_is_idempotent(session: Session) -> None:
    first = crud.get_lora_settings(session=session)
    second = crud.get_lora_settings(session=session)

    assert first.id == second.id == 1


def test_update_lora_settings_partial(session: Session) -> None:
    crud.get_lora_settings(session=session)
    original = crud.get_lora_settings(session=session)
    original_updated_at = original.updated_at

    updated = crud.update_lora_settings(
        session=session, settings_in=LoraSettingsUpdate(channel=10, is_active=True)
    )

    assert updated.channel == 10
    assert updated.is_active is True
    # Untouched fields keep their value: PATCH is partial.
    assert updated.speed == 2
    assert updated.updated_at >= original_updated_at


def test_update_lora_settings_without_prior_read_still_targets_singleton(
    session: Session,
) -> None:
    updated = crud.update_lora_settings(
        session=session, settings_in=LoraSettingsUpdate(speed=5)
    )

    assert updated.id == 1
    assert updated.speed == 5
