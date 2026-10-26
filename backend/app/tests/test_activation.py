from app.services.activation import apply_active_state


def test_apply_active_state_audio_device_activates_without_raising() -> None:
    apply_active_state(
        device_id="lumestrio3", active=True, handles_audio=True, handles_dmx=False, audiofile="x.mp3"
    )


def test_apply_active_state_dmx_device_activates_without_raising() -> None:
    apply_active_state(device_id="lumestrio3", active=True, handles_audio=False, handles_dmx=True)


def test_apply_active_state_plain_device_activates_without_raising() -> None:
    apply_active_state(device_id="relaystrio5", active=True, handles_audio=False, handles_dmx=False)


def test_apply_active_state_deactivates_without_raising() -> None:
    apply_active_state(device_id="lumestrio3", active=False, handles_audio=True, handles_dmx=True)
