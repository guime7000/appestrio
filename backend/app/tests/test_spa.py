from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import mount_spa


def _build_spa_app(static_dir: Path) -> FastAPI:
    app = FastAPI()
    mount_spa(app, static_dir)
    return app


def test_mount_spa_serves_index_for_unknown_routes(tmp_path: Path) -> None:
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "app.js").write_text("console.log('hi')")
    (tmp_path / "index.html").write_text("<html>spa</html>")

    client = TestClient(_build_spa_app(tmp_path))

    response = client.get("/devices")

    assert response.status_code == 200
    assert response.text == "<html>spa</html>"


def test_mount_spa_serves_assets(tmp_path: Path) -> None:
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "app.js").write_text("console.log('hi')")
    (tmp_path / "index.html").write_text("<html>spa</html>")

    client = TestClient(_build_spa_app(tmp_path))

    response = client.get("/assets/app.js")

    assert response.status_code == 200
    assert "console.log" in response.text


def test_mount_spa_does_not_shadow_api_404s(tmp_path: Path) -> None:
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<html>spa</html>")

    app = FastAPI()

    @app.get("/api/v1/known")
    def known() -> dict[str, str]:
        return {"ok": "yes"}

    mount_spa(app, tmp_path)
    client = TestClient(app)

    response = client.get("/api/v1/unknown")

    assert response.status_code == 404
    assert response.text != "<html>spa</html>"


def test_mount_spa_noop_when_directory_missing(tmp_path: Path) -> None:
    app = _build_spa_app(tmp_path / "does-not-exist")
    client = TestClient(app)

    response = client.get("/devices")

    assert response.status_code == 404
