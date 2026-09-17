from lora_daemon import messages as m
from lora_daemon.transport import LoopbackBus, LoopbackTransport


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
