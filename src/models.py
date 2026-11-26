from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


def current_time() -> datetime:
    return datetime.now(timezone.utc)


class Conversation(SQLModel, table=True):
    id: str = Field(
        primary_key=True,
        max_length=64
    )

    created_at: datetime = Field(
        default_factory=current_time,
        nullable=False
    )


class Turn(SQLModel, table=True):

    id: Optional[int] = Field(
        default=None,
        primary_key=True
    )

    thread_id: str = Field(
        foreign_key="conversation.id",
        max_length=64,
        index=True
    )

    question: str
    answer: str

    decision: Optional[str] = Field(
        default=None,
        max_length=16
    )

    comment: Optional[str] = Field(
        default=None,
        max_length=500
    )

    created_at: datetime = Field(
        default_factory=current_time,
        nullable=False
    )