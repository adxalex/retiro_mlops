from config import DATABASE_URL

from sqlmodel import Session, SQLModel, create_engine, select
from src.models import Conversation, Message

from typing import Any

engine = create_engine(DATABASE_URL, echo=False)


def build_tables() -> None:
    SQLModel.metadata.create_all(engine)


def turn_upload(*,thread_id: str, pregunta: str, respuesta: str,decision:str|None,comentario:str|None) -> None:
    with Session(engine) as session:
        if session.get(Conversation, thread_id) is None:
            session.add(Conversation(id=thread_id))
            session.commit()
        session.add(Message(thread_id=thread_id, role="user", content=pregunta))
        session.add(Message(thread_id=thread_id, role="assistant", content=respuesta,decision=decision,comment=comentario))
        session.commit()


def messages_thread(thread_id: str) -> list[dict[str, Any]]:
    with Session(engine) as session:
        mgs = session.exec(select(Message).where(Message.thread_id == thread_id).order_by(Message.id)).all()
    return [{
            "role": m.role,
            "content": m.content,
            "decision": m.decision,
            "comment":m.comment,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        } for m in mgs]