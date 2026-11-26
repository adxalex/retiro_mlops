from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from src.db import TurnRepository
from src.models import Conversation, Turn

from sqlalchemy import inspect
from src.db import TurnRepository, make_repository


@pytest.fixture
def engine():
    """Base SQLite en memoria compartida por las sesiones del test."""
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(test_engine)
    yield test_engine
    test_engine.dispose()


@pytest.fixture
def repository(engine):
    return TurnRepository(engine)


def test_guardar_y_listar(repository, engine):
    """Guarda varios turnos y los devuelve del más antiguo al más reciente."""
    thread_id = "thread-orden"

    repository.save(
        thread_id, "Primera pregunta", "Primera respuesta", None, None
    )
    repository.save(
        thread_id, "Segunda pregunta", "Segunda respuesta", "aprobado", ""
    )
    repository.save(
        thread_id, "Tercera pregunta", "Tercera respuesta", "rechazado",
        "No procede",
    )

    # Forzamos fechas no coincidentes con el orden de inserción para verificar
    # que list() ordena por created_at y no por el ID autoincremental.
    with Session(engine) as session:
        turns = session.exec(
            select(Turn).where(Turn.thread_id == thread_id)
        ).all()
        base = datetime(2026, 1, 1, tzinfo=timezone.utc)
        turns[0].created_at = base + timedelta(minutes=2)
        turns[1].created_at = base
        turns[2].created_at = base + timedelta(minutes=1)
        session.add_all(turns)
        session.commit()

    result = repository.list(thread_id)

    assert [turn.question for turn in result] == [
        "Segunda pregunta",
        "Tercera pregunta",
        "Primera pregunta",
    ]
    assert all(turn.thread_id == thread_id for turn in result)
    assert all(turn.created_at.tzinfo is not None for turn in result)


def test_guardar_turno_rechazado(repository, engine):
    """Un rechazo conserva la decisión y el comentario asociado."""
    thread_id = "thread-rechazado"

    repository.save(
        thread_id,
        "¿Instalamos el elemento?",
        "Propongo instalarlo.",
        "rechazado",
        "No cumple los criterios.",
    )

    turns = repository.list(thread_id)

    assert len(turns) == 1
    assert turns[0].decision == "rechazado"
    assert turns[0].comment == "No cumple los criterios."

    with Session(engine) as session:
        conversation = session.get(Conversation, thread_id)
        assert conversation is not None


def test_guardar_turno_informativo(repository):
    """Los turnos informativos admiten decision y comment nulos."""
    thread_id = "thread-informativo"

    repository.save(
        thread_id,
        "¿Cuál es el horario?",
        "El parque abre a las 6:00.",
        None,
        None,
    )

    turns = repository.list(thread_id)

    assert len(turns) == 1
    assert turns[0].decision is None
    assert turns[0].comment is None


def test_list_hilo_sin_turnos(repository):
    """Un hilo sin turnos devuelve una lista vacía."""
    assert repository.list("thread-vacio") == []


def test_persiste_entre_repositorios(engine):
    """Dos repositorios sobre el mismo motor comparten el historial."""
    first_repository = TurnRepository(engine)
    second_repository = TurnRepository(engine)
    thread_id = "thread-reinicio"

    first_repository.save(
        thread_id, "Pregunta persistida", "Respuesta persistida", None, None
    )

    turns = second_repository.list(thread_id)

    assert len(turns) == 1
    assert turns[0].thread_id == thread_id
    assert turns[0].question == "Pregunta persistida"
    assert turns[0].answer == "Respuesta persistida"


def test_varios_turnos_comparten_una_conversacion(repository, engine):
    """Varios turnos con el mismo thread_id crean una sola Conversation."""
    thread_id = "thread-unico"

    repository.save(thread_id, "Pregunta 1", "Respuesta 1", None, None)
    repository.save(thread_id, "Pregunta 2", "Respuesta 2", None, None)

    with Session(engine) as session:
        conversations = session.exec(
            select(Conversation).where(Conversation.id == thread_id)
        ).all()
        turns = session.exec(
            select(Turn).where(Turn.thread_id == thread_id)
        ).all()

    assert len(conversations) == 1
    assert len(turns) == 2
    assert all(turn.thread_id == conversations[0].id for turn in turns)

def test_ping_sano(engine):
    repository = TurnRepository(engine)

    assert repository.ping() is True

def test_ping_motor_roto_no_lanza(tmp_path):
    broken_path = tmp_path / "missing" / "database.db"

    broken_engine = create_engine(
        f"sqlite:///{broken_path.as_posix()}"
    )

    repository = TurnRepository(broken_engine)

    try:
        assert repository.ping() is False
    finally:
        broken_engine.dispose()

def test_save_y_list_lanzan_con_motor_roto(tmp_path):
    broken_path = tmp_path / "missing" / "database.db"

    broken_engine = create_engine(
        f"sqlite:///{broken_path.as_posix()}"
    )

    repository = TurnRepository(broken_engine)

    try:
        with pytest.raises(Exception):
            repository.save(
                "thread-error",
                "Pregunta",
                "Respuesta",
                None,
                None,
            )

        with pytest.raises(Exception):
            repository.list("thread-error")

    finally:
        broken_engine.dispose()

def test_tablas_se_crean_perezosamente():
    lazy_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    try:
        repository = TurnRepository(lazy_engine)

        # Al crear el repositorio todavía no existen tablas.
        assert inspect(lazy_engine).get_table_names() == []

        # Primer uso: guardar un turno.
        repository.save(
            "thread-lazy",
            "Pregunta",
            "Respuesta",
            None,
            None,
        )

        # Ahora deben existir ambas tablas.
        tables = inspect(lazy_engine).get_table_names()

        assert "conversation" in tables
        assert "turn" in tables

    finally:
        lazy_engine.dispose()

def test_make_repository_usa_motor_configurado(monkeypatch, engine):
    import src.db as db

    monkeypatch.setattr(
        db,
        "make_engine",
        lambda url=None: engine,
    )

    repository = make_repository()

    assert isinstance(repository, TurnRepository)
    assert repository.engine is engine
