from datetime import UTC, datetime
from uuid import UUID

from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(UTC)


class Message(SQLModel):
    message: str


class BulkDeleteRequest(SQLModel):
    uuids: list[UUID] = Field(min_length=1)
