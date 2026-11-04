from pathlib import Path

import httpx
import pytest

from app.core.config import settings
from app.services import qlc_files
from app.services.qlc_files import _push_live_reload as _real_push_live_reload


@pytest.fixture(autouse=True)
def _isolate_qlc_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "QLC_PROJECT_DIR", str(tmp_path / "qlc"))
    # Real _push_live_reload opens a real network connection to
    # "qlcplus:9999" -- not reachable in this sandbox. Tests that care
    # about the live-reload call itself override this.
    monkeypatch.setattr(qlc_files, "_push_live_reload", lambda _path: None)


def test_save_project_writes_the_file() -> None:
    path = qlc_files.save_project("show.qxw", b"<Workspace/>")

    assert path.read_bytes() == b"<Workspace/>"
    assert path.parent == qlc_files.project_dir()


def test_save_project_replaces_any_existing_project_file() -> None:
    qlc_files.save_project("old_show.qxw", b"old")

    qlc_files.save_project("new_show.qxw", b"new")

    remaining = sorted(qlc_files.project_dir().glob("*.qxw"))
    assert len(remaining) == 1
    assert remaining[0].name == "new_show.qxw"
    assert remaining[0].read_bytes() == b"new"


def test_save_project_does_not_touch_fixtures() -> None:
    qlc_files.save_fixture("lyre.qxf", b"fixture")

    qlc_files.save_project("show.qxw", b"<Workspace/>")

    assert (qlc_files.fixtures_dir() / "lyre.qxf").exists()


def test_save_fixture_writes_into_the_fixtures_subfolder() -> None:
    path = qlc_files.save_fixture("lyre.qxf", b"<FixtureDefinition/>")

    assert path.parent == qlc_files.fixtures_dir()
    assert path.read_bytes() == b"<FixtureDefinition/>"


def test_save_fixture_is_additive() -> None:
    qlc_files.save_fixture("one.qxf", b"1")
    qlc_files.save_fixture("two.qxf", b"2")

    names = {p.name for p in qlc_files.fixtures_dir().glob("*.qxf")}
    assert names == {"one.qxf", "two.qxf"}


def test_save_project_pushes_a_live_reload(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[Path] = []
    monkeypatch.setattr(qlc_files, "_push_live_reload", seen.append)

    path = qlc_files.save_project("show.qxw", b"<Workspace/>")

    assert seen == [path]


def test_save_fixture_does_not_push_a_live_reload(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[Path] = []
    monkeypatch.setattr(qlc_files, "_push_live_reload", seen.append)

    qlc_files.save_fixture("lyre.qxf", b"fixture")

    assert seen == []


def test_push_live_reload_survives_qlcplus_unreachable(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(*_args, **_kwargs):
        raise httpx.ConnectError("refused")

    class _FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

        def post(self, *_args, **_kwargs):
            _raise()

    monkeypatch.setattr(httpx, "Client", lambda **_kw: _FakeClient())

    path = qlc_files.project_dir() / "show.qxw"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"<Workspace/>")

    _real_push_live_reload(path)  # must not raise -- bypasses the autouse no-op
