from lora_daemon.hexconf import DEFAULT_HEX_CONF, build_hex_conf


def test_default_state_reproduces_default_hex_conf() -> None:
    assert build_hex_conf(channel=40, speed=3, fec=True) == DEFAULT_HEX_CONF


def test_fec_false_clears_option_bit() -> None:
    with_fec = build_hex_conf(channel=40, speed=3, fec=True)
    without_fec = build_hex_conf(channel=40, speed=3, fec=False)
    assert with_fec != without_fec
    # Only the option byte (index 5, i.e. hex chars 10-11) should differ.
    assert with_fec[:10] == without_fec[:10]


def test_different_channels_change_only_the_channel_byte() -> None:
    chan_40 = build_hex_conf(channel=40, speed=3, fec=True)
    chan_54 = build_hex_conf(channel=54, speed=3, fec=True)
    assert chan_40 != chan_54
    # Byte index 4 is hex chars 8-9.
    assert chan_40[:8] == chan_54[:8]
    assert chan_40[10:] == chan_54[10:]


def test_different_speeds_change_only_the_speed_byte() -> None:
    speed_3 = build_hex_conf(channel=40, speed=3, fec=True)
    speed_0 = build_hex_conf(channel=40, speed=0, fec=True)
    assert speed_3 != speed_0
    # Byte index 3 is hex chars 6-7.
    assert speed_3[:6] == speed_0[:6]
    assert speed_3[8:] == speed_0[8:]
