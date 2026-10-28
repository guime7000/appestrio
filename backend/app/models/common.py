from datetime import UTC, datetime
from uuid import UUID

from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(UTC)


class Message(SQLModel):
    message: str


class BulkDeleteRequest(SQLModel):
    uuids: list[UUID] = Field(min_length=1)


class WhoAmI(SQLModel):
    is_master: bool


class AgendaDisabledRequest(SQLModel):
    """Body for `POST /agenda/disabled` -- the reverse channel
    `lora-daemon` calls on every DISABLE_AGENDA frame (and every
    broadcast ACTIVATE, which implicitly disables the agenda too) so
    item 7's local evaluator knows to pause (Docs/To_Be_Done.md item 7).
    """

    disabled: bool
