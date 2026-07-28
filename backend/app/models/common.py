from datetime import UTC, datetime

from sqlmodel import SQLModel


def utcnow() -> datetime:
    return datetime.now(UTC)


class Message(SQLModel):
    message: str
