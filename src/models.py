from datetime import datetime, timezone

from sqlmodel import Field, SQLModel
from typing import Optional

def current_time() -> datetime:
    return datetime.now(timezone.utc)


class Conversation(SQLModel, table=True):

    id: str = Field(primary_key=True, max_length=150)
    time_stamp: datetime = Field(default_factory=current_time)


class Message(SQLModel, table=True):

    id: Optional[int] = Field(primary_key=True,default=None)
    thread_id: str = Field(foreign_key="conversation.id", max_length=150,index=True)
    role: str = Field(max_length=30)
    content: str
    time_stamp: datetime = Field(default_factory=current_time)