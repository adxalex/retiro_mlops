from sqlmodel import Session, create_engine, select

import config
from src.models import Conversation, Turn


def normalize_database_url(url: str) -> str:

    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]

    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]

    return url


def make_engine(url: str | None = None):

    database_url = config.DATABASE_URL if url is None else url
    database_url = normalize_database_url(database_url)

    if database_url.startswith("postgresql"):
        return create_engine(
            database_url,
            connect_args={
                "connect_timeout": config.DB_CONNECT_TIMEOUT_SECONDS
            },
        )

    return create_engine(database_url)


class TurnRepository:


    def __init__(self, engine) -> None:
        self.engine = engine

    def save(
        self,
        thread_id: str,
        question: str,
        answer: str,
        decision: str | None,
        comment: str | None,
    ) -> None:


        with Session(self.engine) as session:

            # Comprobar si existe la conversación.
            conversation = session.get(Conversation, thread_id)

            # Crear la conversación si todavía no existe.
            if conversation is None:
                conversation = Conversation(id=thread_id)
                session.add(conversation)
                session.flush()

            # Crear el turno asociado a la conversación.
            turn = Turn(
                thread_id=thread_id,
                question=question,
                answer=answer,
                decision=decision,
                comment=comment,
            )

            session.add(turn)
            session.commit()

    def list(self, thread_id: str) -> list:


        with Session(self.engine) as session:
            statement = (
                select(Turn)
                .where(Turn.thread_id == thread_id)
                .order_by(Turn.created_at.asc(), Turn.id.asc())
            )

            return list(session.exec(statement).all())