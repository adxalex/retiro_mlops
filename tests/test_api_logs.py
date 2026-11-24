
import logging

from fastapi import FastAPI
from fastapi.testclient import TestClient

from security import (
    ApiKeyMaskingFilter,
    RateLimiter,
    SecurityGateMiddleware,
)

import pytest
import config
from api import create_app


API_KEY = "clave-super-secreta-de-prueba"


def create_test_app():
    app = FastAPI()

    app.add_middleware(
        SecurityGateMiddleware,
        api_key=API_KEY,
        limiter=RateLimiter(limit=30, clock=lambda: 0),
        protected_paths={"/private"},
    )

    @app.get("/private")
    def private(thread_id: str):
        return {"message": "ok"}

    return app


def test_peticion_protegida_genera_un_log_con_los_campos_requeridos(caplog):
    app = create_test_app()

    with caplog.at_level(logging.INFO, logger="security"):
        with TestClient(app) as client:
            response = client.get(
                "/private",
                params={
                    "api_key": API_KEY,
                    "thread_id": "hilo-123",
                },
            )

    assert response.status_code == 200

    # Debe existir exactamente un log de la petición protegida.
    records = [
        record
        for record in caplog.records
        if record.name == "security"
    ]
    assert len(records) == 1

    record = records[0]

    assert record.method == "GET"
    assert record.path == "/private"
    assert record.thread_id == "hilo-123"
    assert isinstance(record.duration_ms, (int, float))
    assert record.duration_ms >= 0
    assert record.status == 200


def test_el_log_no_contiene_la_api_key(caplog):
    app = create_test_app()

    with caplog.at_level(logging.INFO, logger="security"):
        with TestClient(app) as client:
            client.get(
                "/private",
                params={
                    "api_key": API_KEY,
                    "thread_id": "hilo-123",
                },
            )

    assert API_KEY not in caplog.text


def test_filtro_enmascara_api_key_en_logs_de_acceso():
    log_filter = ApiKeyMaskingFilter()

    record = logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg='GET /private?api_key=clave-super-secreta HTTP/1.1',
        args=(),
        exc_info=None,
    )

    assert log_filter.filter(record) is True

    mensaje = record.getMessage()

    assert "clave-super-secreta" not in mensaje
    assert "api_key=***" in mensaje


def test_app_real_registra_log_por_peticion_protegida(
    caplog,
    monkeypatch,
    in_memory_repo,
    fake_agent,
):
    api_key = "clave-prueba-log"
    monkeypatch.setattr(config, "API_KEY", api_key)

    app = create_app(repo=in_memory_repo, agent=fake_agent)

    with caplog.at_level(logging.INFO, logger="security"):
        with TestClient(app) as client:
            response = client.get(
                "/threads/hilo-prueba",
                params={"api_key": api_key},
            )

    assert response.status_code != 401

    registros = [
        record
        for record in caplog.records
        if record.name == "security"
    ]

    assert len(registros) == 1
    assert registros[0].method == "GET"
    assert registros[0].path == "/threads/hilo-prueba"
    assert registros[0].status == response.status_code
    assert api_key not in caplog.text
