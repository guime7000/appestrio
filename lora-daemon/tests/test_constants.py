import pytest

from lora_daemon.constants import MessageType, get_num_in_ping


def test_message_type_values_match_legacy_declaration_order() -> None:
    # Legacy: `enum MessageType { SYNC = 1, PING, PONG, ACTIVATE,
    # DISABLE_AGENDA, FILE_MSG }` -- TS auto-increments from 1.
    assert MessageType.SYNC == 1
    assert MessageType.PING == 2
    assert MessageType.PONG == 3
    assert MessageType.ACTIVATE == 4
    assert MessageType.DISABLE_AGENDA == 5
    assert MessageType.FILE_MSG == 6


def test_get_num_in_ping_matches_legacy_default_interval() -> None:
    # Default pingUpdateIntervalSec = 5s -> 5000ms; legacy's own constants
    # give floor((5000-500-400)/500) = 8.
    assert get_num_in_ping(5000) == 8


def test_get_num_in_ping_rejects_too_short_interval() -> None:
    with pytest.raises(ValueError, match="invalid ping time"):
        get_num_in_ping(100)
