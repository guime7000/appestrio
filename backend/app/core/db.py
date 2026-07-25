from sqlmodel import SQLModel, create_engine

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


def init_db() -> None:
    # No Alembic migrations exist yet, so create the tables directly from
    # the SQLModel metadata. Switch to `alembic upgrade head` once migrations
    # are introduced.
    SQLModel.metadata.create_all(engine)
