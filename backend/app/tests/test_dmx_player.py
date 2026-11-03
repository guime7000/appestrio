import pytest

from app.services import dmx_player
from app.services.dmx_player import DmxPlayerError


class _FakeWebSocket:
    def __init__(self, functions: dict[int, tuple[str, str]]) -> None:
        # functions: {id: (name, type)}
        self._functions = functions
        self.sent: list[str] = []
        self.closed = False

    def send(self, message: str) -> None:
        self.sent.append(message)

    def recv(self) -> str:
        message = self.sent[-1]
        parts = message.split("|")
        if parts[1] == "getFunctionsList":
            flat = []
            for fid, (name, _type) in self._functions.items():
                flat.extend([str(fid), name])
            return "QLC+API|getFunctionsList|" + "|".join(flat)
        if parts[1] == "getFunctionType":
            fid = int(parts[2])
            return f"QLC+API|getFunctionType|{self._functions[fid][1]}"
        raise AssertionError(f"unexpected message in test double: {message}")

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def fake_ws(monkeypatch: pytest.MonkeyPatch):
    def _install(functions: dict[int, tuple[str, str]]) -> _FakeWebSocket:
        ws = _FakeWebSocket(functions)
        monkeypatch.setattr(dmx_player, "_connect", lambda: ws)
        return ws

    return _install


def test_start_show_sets_every_show_function_to_running(fake_ws) -> None:
    ws = fake_ws(
        {
            0: ("fenetre bleu", "Scene"),
            2: ("Nouveau spectacle 2", "Show"),
            3: ("Nouveau spectacle 3", "Show"),
            7: ("test mvt couleur", "Chaser"),
        }
    )

    dmx_player.start_show()

    assert "QLC+API|setFunctionStatus|2|1" in ws.sent
    assert "QLC+API|setFunctionStatus|3|1" in ws.sent
    assert not any("setFunctionStatus|0|" in m or "setFunctionStatus|7|" in m for m in ws.sent)
    assert ws.closed


def test_stop_show_sets_every_show_function_to_stopped(fake_ws) -> None:
    ws = fake_ws({2: ("Nouveau spectacle 2", "Show")})

    dmx_player.stop_show()

    assert "QLC+API|setFunctionStatus|2|0" in ws.sent


def test_start_show_with_no_show_function_warns_and_sends_nothing(fake_ws) -> None:
    ws = fake_ws({0: ("fenetre bleu", "Scene")})

    dmx_player.start_show()

    assert not any("setFunctionStatus" in m for m in ws.sent)


def test_connect_failure_raises_dmx_player_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise_connect():
        raise DmxPlayerError("couldn't connect to QLC+ at ws://qlcplus:9999/qlcplusWS: refused")

    monkeypatch.setattr(dmx_player, "_connect", _raise_connect)

    with pytest.raises(DmxPlayerError):
        dmx_player.start_show()
