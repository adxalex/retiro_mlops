from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine, select

import config
from src.models import Conversation, Turn


def normalize_database_url(url: str) -> str:
    """Normaliza las URL de PostgreSQL para utilizar psycopg 3."""

    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]

    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]

    return url


def make_engine(url: str | None = None):
    """Crea el motor de base de datos."""

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
    """Repositorio para gestionar conversaciones y turnos."""

    def __init__(self, engine) -> None:
        self.engine = engine

    def _ensure_tables(self) -> None:
        """Crea las tablas cuando se utilizan por primera vez."""
        SQLModel.metadata.create_all(self.engine)

    def ping(self) -> bool:
        """Comprueba la conexión sin propagar excepciones."""

        try:
            with self.engine.connect() as connection:
                connection.execute(text("SELECT 1"))

            return True

        except Exception:
            return False

    def save(
        self,
        thread_id: str,
        question: str,
        answer: str,
        decision: str | None,
        comment: str | None,
    ) -> None:
        """Guarda un turno asociado a una conversación."""

        self._ensure_tables()

        with Session(self.engine) as session:

            conversation = session.get(Conversation, thread_id)

            if conversation is None:
                conversation = Conversation(id=thread_id)
                session.add(conversation)
                session.flush()

            turn = Turn(
                thread_id=thread_id,
                question=question,
                answer=answer,
                decision=decision,
                comment=comment,
            )

            session.add(turn)
            session.commit()

    def list(self, thread_id: str) -> list[Turn]:
        """Recupera los turnos de una conversación ordenados cronológicamente."""

        self._ensure_tables()

        with Session(self.engine) as session:
            statement = (
                select(Turn)
                .where(Turn.thread_id == thread_id)
                .order_by(Turn.created_at.asc(), Turn.id.asc())
            )

            return list(session.exec(statement).all())


def make_repository(url: str | None = None) -> TurnRepository:
    """Construye el repositorio utilizando el motor configurado."""

    engine = make_engine(url)

    return TurnRepository(engine)