from lora_daemon.structs import FileReceiver, PingableList


def test_pingable_list_set_and_keys() -> None:
    plist = PingableList()
    assert plist.set_pingable(1, True) is True  # first entry
    assert plist.set_pingable(2, True) is False  # not first anymore
    assert sorted(plist.keys()) == [1, 2]


def test_pingable_list_remove() -> None:
    plist = PingableList()
    plist.set_pingable(1, True)
    plist.set_pingable(1, False)
    assert plist.keys() == []


def test_pingable_list_removes_old_ones() -> None:
    plist = PingableList(keep_alive_s=0)
    plist.set_pingable(1, True)
    plist.remove_old_ones()
    assert plist.keys() == []


def test_file_receiver_reassembles_in_order() -> None:
    receiver = FileReceiver()
    receiver.start(3)
    assert receiver.is_ignoring() is False
    assert receiver.add_part(0, b"foo") is None
    assert receiver.add_part(1, b"bar") is None
    result = receiver.add_part(2, b"baz")
    assert result == "foobarbaz"


def test_file_receiver_reassembles_out_of_order() -> None:
    receiver = FileReceiver()
    receiver.start(3)
    receiver.add_part(2, b"baz")
    receiver.add_part(0, b"foo")
    result = receiver.add_part(1, b"bar")
    assert result == "foobarbaz"


def test_file_receiver_ignore_mode() -> None:
    receiver = FileReceiver()
    receiver.ignore()
    assert receiver.is_ignoring() is True
    assert receiver.add_part(0, b"foo") is None


def test_file_receiver_missing_ids() -> None:
    receiver = FileReceiver()
    receiver.start(3)
    receiver.add_part(1, b"bar")
    assert receiver.missing_ids() == [0, 2]


def test_file_receiver_clean_up_resets_to_ignoring() -> None:
    receiver = FileReceiver()
    receiver.start(2)
    receiver.clean_up()
    assert receiver.is_ignoring() is True
