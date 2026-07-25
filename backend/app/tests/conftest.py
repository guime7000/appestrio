import os

# Force the app's real engine onto an in-memory DB before app.core.config is
# ever imported, so importing app.main during tests never touches the dev
# SQLITE_PATH file on disk. Tests themselves talk to their own isolated
# engine (see the `session` fixture below), not this one.
os.environ.setdefault("SQLITE_PATH", ":memory:")
os.environ.setdefault("PROJECT_NAME", "Appestrio Test")

from collections.abc import Generator  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402
from sqlmodel import Session, SQLModel, create_engine  # noqa: E402

from app.api.deps import get_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(name="session")
def session_fixture() -> Generator[Session]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session) -> Generator[TestClient]:
    def get_db_override() -> Generator[Session]:
        yield session

    app.dependency_overrides[get_db] = get_db_override
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
