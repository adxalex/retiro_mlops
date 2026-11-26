from datetime import datetime, timezone

from sqlmodel import SQLModel, Session, create_engine, select
from sqlalchemy import inspect

from src.models import Conversation, Turn


def test_create_tables():
    """Comprueba que se crean las dos tablas."""

    engine = create_engine("sqlite:///:memory:")

    SQLModel.metadata.create_all(engine)

    inspector = inspect(engine)
    tables = inspector.get_table_names()

    assert "conversation" in tables
    assert "turn" in tables

    engine.dispose()


def test_conversation_fields():
    """Comprueba los campos de Conversation."""

    conversation = Conversation(id="thread_001")

    assert conversation.id == "thread_001"
    assert isinstance(conversation.created_at, datetime)


def test_turn_fields():
    """Comprueba los campos del contrato Turn."""

    turn = Turn(
        thread_id="thread_001",
        question="¿Cuál es el horario?",
        answer="Abre a las 6:00.",
        decision="aprobado",
        comment="Consulta informativa"
    )

    assert turn.thread_id == "thread_001"
    assert turn.question == "¿Cuál es el horario?"
    assert turn.answer == "Abre a las 6:00."
    assert turn.decision == "aprobado"
    assert turn.comment == "Consulta informativa"
    assert isinstance(turn.created_at, datetime)


def test_created_at_utc():
    """Comprueba que created_at utiliza UTC."""

    turn = Turn(
        thread_id="thread_001",
        question="Pregunta",
        answer="Respuesta"
    )

    assert turn.created_at.tzinfo is not None
    assert turn.created_at.utcoffset().total_seconds() == 0


def test_decision_and_comment_can_be_none():
    """Comprueba que decision y comment admiten None."""

    turn = Turn(
        thread_id="thread_001",
        question="Pregunta",
        answer="Respuesta",
        decision=None,
        comment=None
    )

    assert turn.decision is None
    assert turn.comment is None


def test_multiple_turns_in_one_conversation():
    """Comprueba la relación 1:N entre Conversation y Turn."""

    engine = create_engine("sqlite:///:memory:")

    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:

        conversation = Conversation(id="thread_001")
        session.add(conversation)
        session.commit()

        turn1 = Turn(
            thread_id="thread_001",
            question="Primera pregunta",
            answer="Primera respuesta"
        )

        turn2 = Turn(
            thread_id="thread_001",
            question="Segunda pregunta",
            answer="Segunda respuesta"
        )

        session.add_all([turn1, turn2])
        session.commit()

        turns = session.exec(
            select(Turn).where(
                Turn.thread_id == "thread_001"
            )
        ).all()

        assert len(turns) == 2

        assert all(
            turn.thread_id == conversation.id
            for turn in turns
        )

    engine.dispose()


def test_turn_foreign_key():
    """Comprueba que thread_id referencia Conversation.id."""

    engine = create_engine("sqlite:///:memory:")

    SQLModel.metadata.create_all(engine)

    inspector = inspect(engine)

    foreign_keys = inspector.get_foreign_keys("turn")

    assert any(
        fk["referred_table"] == "conversation"
        and fk["constrained_columns"] == ["thread_id"]
        and fk["referred_columns"] == ["id"]
        for fk in foreign_keys
    )

    engine.dispose()