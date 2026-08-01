from pathlib import Path

from alembic.command import upgrade
from alembic.config import Config
from sqlmodel import create_engine

from app.core.config import settings

# check_same_thread=False is required for SQLite when the same connection
# may be used by more than one FastAPI worker thread.
engine = create_engine(
    str(settings.SQLALCHEMY_DATABASE_URI),
    connect_args={"check_same_thread": False},
)


# make sure all SQLModel models are imported (app.models) before initializing DB
# otherwise, SQLModel might fail to initialize relationships properly
# for more details: https://github.com/fastapi/full-stack-fastapi-template/issues/28
from app import models  # noqa: E402, F401

BACKEND_DIR = Path(__file__).resolve().parents[2]


def init_db() -> None:
    # Resolve paths explicitly (rather than relying on cwd) so this works
    # regardless of where the process is started from.
    alembic_cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(BACKEND_DIR / "app" / "alembic"))
    upgrade(alembic_cfg, "head")
