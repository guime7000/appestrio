import os
import socket

from lora_daemon import messages as m
from lora_daemon.transport import LoopbackBus, LoopbackTransport, LoraSocketTransport


def test_loopback_delivers_to_other_transports_not_sender() -> None:
    bus = LoopbackBus()
    master = LoopbackTransport(bus)
    device = LoopbackTransport(bus)

    master.send(m.encode_activate(True, [3]))

    assert master.receive_all() == []  # a device never hears its own send
    received = device.receive_all()
    assert len(received) == 1
    assert m.decode_activate(received[0]) == m.Activate(active=True, addresses=(3,))


def test_loopback_broadcasts_to_every_other_transport() -> None:
    bus = LoopbackBus()
    master = LoopbackTransport(bus)
    device_a = LoopbackTransport(bus)
    device_b = LoopbackTransport(bus)

    master.send(m.encode_disable_agenda(True))

    for device in (device_a, device_b):
        [received] = device.receive_all()
        assert m.decode_disable_agenda(received) is True


def test_loopback_round_trips_multiple_messages_in_order() -> None:
    bus = LoopbackBus()
    sender = LoopbackTransport(bus)
    receiver = LoopbackTransport(bus)

    sender.send(m.encode_disable_agenda(True))
    sender.send(m.encode_disable_agenda(False))

    received = receiver.receive_all()
    assert [m.decode_disable_agenda(b) for b in received] == [True, False]


def test_receive_all_drains_the_inbox() -> None:
    bus = LoopbackBus()
    sender = LoopbackTransport(bus)
    receiver = LoopbackTransport(bus)

    sender.send(m.encode_disable_agenda(True))
    receiver.receive_all()

    assert receiver.receive_all() == []


def test_lora_socket_transport_creates_missing_client_socket_dir(tmp_path) -> None:
    # e32_socket_path must exist and be listening for open()'s registration
    # datagram to succeed -- a fake stand-in for e32.service here.
    e32_path = str(tmp_path / "e32.data")
    fake_e32 = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    fake_e32.bind(e32_path)

    client_path = str(tmp_path / "nested" / "does" / "not" / "exist" / "client.sock")
    transport = LoraSocketTransport(client_socket_path=client_path, e32_socket_path=e32_path)

    try:
        transport.open()
        assert os.path.exists(client_path)
    finally:
        transport.close()
        fake_e32.close()
