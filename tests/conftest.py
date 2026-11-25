"""Configuracion comun de las pruebas.

Los tests llaman a responder(), que registra cada consulta en
output/consultas.jsonl. Sin esta proteccion, una ejecucion de la suite deja
cientos de entradas falsas en el registro real y las metricas del informe
quedan inservibles: se midio un tiempo medio de 0,465 s cuando una consulta
real tarda entre 6 y 15 s.

Esta fixture redirige el registro a un fichero temporal en todas las pruebas.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def log_aislado(tmp_path, monkeypatch):
    """Ninguna prueba debe escribir en el registro real de consultas."""
    from src import logging_utils

    monkeypatch.setattr(
        logging_utils, "RUTA_LOG", tmp_path / "consultas_de_prueba.jsonl"
    )

from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi.testclient import TestClient


@dataclass
class FakeTurn:
    """Representa un turno guardado durante las pruebas."""

    thread_id: str
    question: str
    answer: str
    decision: str | None
    comment: str | None
    created_at: datetime


class InMemoryTurnRepository:
    """Repositorio en memoria que simula el comportamiento de PostgreSQL."""

    def __init__(self, falla=False):
        self.falla = falla
        self.turnos = []

    def ping(self):
        """Comprueba si el repositorio está disponible."""
        return not self.falla

    def save(self, thread_id, question, answer, decision, comment):
        """Guarda un turno en memoria."""
        if self.falla:
            raise RuntimeError("Error simulado de base de datos")

        turno = FakeTurn(
            thread_id=thread_id,
            question=question,
            answer=answer,
            decision=decision,
            comment=comment,
            created_at=datetime.now(timezone.utc),
        )
        self.turnos.append(turno)

    def list(self, thread_id):
        """Devuelve los turnos de un hilo, del más antiguo al más reciente."""
        if self.falla:
            raise RuntimeError("Error simulado de base de datos")

        return [
            turno
            for turno in self.turnos
            if turno.thread_id == thread_id
        ]


class FakeAgent:
    """Agente falso para probar la API sin ejecutar el agente real."""

    def procesar_turno(self, texto, thread_id, imagen=None):
        return {
            "thread_id": thread_id,
            "respuesta": "Respuesta de prueba",
            "plan": [],
            "pendiente_aprobacion": False,
            "done": True,
            "traza": [],
            "error": None,
        }

    def aprobar_plan(self, thread_id, aprobado, comentario=""):
        return {
            "thread_id": thread_id,
            "respuesta": "Respuesta de prueba",
            "plan": [],
            "pendiente_aprobacion": False,
            "done": True,
            "traza": [],
            "error": None,
        }


@pytest.fixture
def fake_agent():
    return FakeAgent()


@pytest.fixture
def in_memory_repo():
    return InMemoryTurnRepository()


@pytest.fixture
def in_memory_repo_roto():
    return InMemoryTurnRepository(falla=True)


@pytest.fixture
def api_client(in_memory_repo, fake_agent, monkeypatch):
    import config

    # API Key ficticia exclusiva para los tests
    monkeypatch.setattr(config, "API_KEY", "test-key")

    from api import create_app
    app = create_app(repo=in_memory_repo, agent=fake_agent)

    with TestClient(app) as client:
        yield client


@pytest.fixture
def api_client_roto(in_memory_repo_roto, fake_agent):
    from api import create_app

    app = create_app(repo=in_memory_repo_roto, agent=fake_agent)

    with TestClient(app) as client:
        yield client
