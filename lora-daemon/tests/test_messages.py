from datetime import datetime

import pytest

from lora_daemon import messages as m
from lora_daemon.constants import BROADCAST_ADDRESS, FILE_MSG_START, MessageType


def test_sync_round_trip() -> None:
    when = datetime(2026, 9, 18, 14, 5, 30)
    buf = m.encode_sync(when)
    assert buf[0] == MessageType.SYNC
    assert m.decode_sync(buf) == "18/09/2026 14:05:30"


def test_ping_round_trip() -> None:
    buf = m.encode_ping(
        agenda_disabled=True,
        ping_type=m.PingType.WITH_AGENDA_MD5,
        disable_wifi=False,
        slot_delay_centisec=50,
        addresses=[3, 7, 40],
    )
    ping = m.decode_ping(buf)
    assert ping.agenda_disabled is True
    assert ping.ping_type == m.PingType.WITH_AGENDA_MD5
    assert ping.disable_wifi is False
    assert ping.slot_delay_ms == 500
    assert ping.addresses == (3, 7, 40)
    assert ping.own_slot(7) == 1
    assert ping.own_slot(99) is None


def test_pong_plain_round_trip() -> None:
    buf = m.encode_pong(address=5, active=True)
    pong = m.decode_pong(buf)
    assert pong == m.Pong(address=5, active=True)


def test_pong_with_agenda_md5_round_trip() -> None:
    buf = m.encode_pong(address=5, active=False, agenda_md5="abcdef1234567890")
    pong = m.decode_pong(buf, expect_agenda_md5=True)
    assert pong.address == 5
    assert pong.active is False
    assert pong.agenda_md5 == "abcdef12"  # truncated to 8 chars, like legacy


def test_pong_with_missing_parts_round_trip() -> None:
    buf = m.encode_pong(address=5, active=True, missing_parts=[0, 2, 4])
    pong = m.decode_pong(buf, expect_missing_parts=True)
    assert pong.missing_parts == (0, 2, 4)


def test_pong_with_missing_parts_empty() -> None:
    buf = m.encode_pong(address=5, active=True, missing_parts=[])
    pong = m.decode_pong(buf, expect_missing_parts=True)
    assert pong.missing_parts == ()


def test_activate_round_trip() -> None:
    buf = m.encode_activate(True, [3, 40])
    activate = m.decode_activate(buf)
    assert activate.active is True
    assert activate.addresses == (3, 40)
    assert activate.targets(3) is True
    assert activate.targets(99) is False
    assert activate.is_multi() is True


def test_activate_defaults_to_broadcast() -> None:
    buf = m.encode_activate(True)
    activate = m.decode_activate(buf)
    assert activate.addresses == (BROADCAST_ADDRESS,)
    assert activate.targets(17) is True
    assert activate.is_multi() is True  # broadcast counts as multi


def test_activate_single_target_is_not_multi() -> None:
    buf = m.encode_activate(False, [3])
    activate = m.decode_activate(buf)
    assert activate.is_multi() is False


def test_disable_agenda_round_trip() -> None:
    assert m.decode_disable_agenda(m.encode_disable_agenda(True)) is True
    assert m.decode_disable_agenda(m.encode_disable_agenda(False)) is False


def test_file_msg_start_round_trip() -> None:
    buf = m.encode_file_msg_start(5, [3, 40])
    decoded = m.decode_file_msg(buf)
    assert isinstance(decoded, m.FileMsgStart)
    assert decoded.num_parts == 5
    assert decoded.addresses == (3, 40)
    assert decoded.targets(3) is True
    assert decoded.targets(99) is False


def test_file_msg_start_defaults_to_broadcast() -> None:
    decoded = m.decode_file_msg(m.encode_file_msg_start(5))
    assert decoded.addresses == (BROADCAST_ADDRESS,)


def test_file_msg_chunk_round_trip() -> None:
    buf = m.encode_file_msg_chunk(2, b"hello")
    decoded = m.decode_file_msg(buf)
    assert isinstance(decoded, m.FileMsgChunk)
    assert decoded.index == 2
    assert decoded.data == b"hello"


def test_file_msg_chunk_index_cannot_collide_with_start_marker() -> None:
    with pytest.raises(m.MalformedMessageError, match="FILE_MSG_START"):
        m.encode_file_msg_chunk(FILE_MSG_START, b"x")


def test_decode_message_dispatches_by_type() -> None:
    ping = m.decode_message(
        m.encode_ping(
            agenda_disabled=False,
            ping_type=m.PingType.PLAIN,
            disable_wifi=False,
            slot_delay_centisec=50,
            addresses=[1],
        )
    )
    assert isinstance(ping, m.Ping)


def test_decode_message_rejects_pong() -> None:
    with pytest.raises(m.MalformedMessageError, match="decode_pong"):
        m.decode_message(m.encode_pong(address=1, active=True))


def test_decode_message_rejects_unknown_type() -> None:
    with pytest.raises(m.MalformedMessageError, match="unknown message type"):
        m.decode_message(bytes([99]))


def test_decode_message_rejects_empty_buffer() -> None:
    with pytest.raises(m.MalformedMessageError, match="empty"):
        m.decode_message(b"")
