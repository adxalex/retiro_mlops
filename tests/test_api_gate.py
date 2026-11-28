
from fastapi import FastAPI
from fastapi.testclient import TestClient

from security import RateLimiter, SecurityGateMiddleware

import logging
import pytest
from fastapi.testclient import TestClient

import config
from api import create_app


API_KEY_CORRECTA = "clave-de-prueba"


def create_test_app(api_key=API_KEY_CORRECTA, limit=30):
    """Crea una aplicación pequeña para probar el control de acceso."""

    app = FastAPI()
    limiter = RateLimiter(limit=limit, clock=lambda: 0)
    app.state.calls = []

    app.add_middleware(
        SecurityGateMiddleware,
        api_key=api_key,
        limiter=limiter,
        protected_paths={"/private"},
    )

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/private")
    def private(q: str):
        app.state.calls.append(q)
        return {"message": "Acceso permitido"}

    return app, limiter


def test_api_key_no_configurada_devuelve_503():
    app, limiter = create_test_app(api_key=None)

    with TestClient(app) as client:
        response = client.get("/private", params={"api_key": API_KEY_CORRECTA, "q": "hola"})

    assert response.status_code == 503
    assert limiter.requests == {}


def test_peticion_sin_api_key_devuelve_401():
    app, limiter = create_test_app()

    with TestClient(app) as client:
        response = client.get("/private", params={"q": "hola"})

    assert response.status_code == 401
    assert limiter.requests == {}


def test_peticion_con_api_key_incorrecta_devuelve_401():
    app, limiter = create_test_app()

    with TestClient(app) as client:
        response = client.get(
            "/private",
            params={"api_key": "clave-incorrecta", "q": "hola"},
        )

    assert response.status_code == 401
    assert limiter.requests == {}


def test_api_key_no_configurada_tiene_prioridad_sobre_401():
    app, _ = create_test_app(api_key=None)

    with TestClient(app) as client:
        response = client.get("/private")

    # Aunque no se envíe api_key, primero debe comprobarse
    # si el servicio tiene una API_KEY configurada.
    assert response.status_code == 503


def test_peticion_valida_llega_al_endpoint():
    app, limiter = create_test_app()

    with TestClient(app) as client:
        response = client.get(
            "/private",
            params={"api_key": API_KEY_CORRECTA, "q": "hola"},
        )

    assert response.status_code == 200
    assert app.state.calls == ["hola"]
    assert API_KEY_CORRECTA in limiter.requests


def test_superar_limite_devuelve_429():
    app, limiter = create_test_app(limit=1)

    with TestClient(app) as client:
        primera = client.get(
            "/private",
            params={"api_key": API_KEY_CORRECTA, "q": "primera"},
        )

        segunda = client.get(
            "/private",
            params={"api_key": API_KEY_CORRECTA, "q": "segunda"},
        )

    assert primera.status_code == 200
    assert segunda.status_code == 429
    assert app.state.calls == ["primera"]


def test_health_es_publico_y_no_consume_limite():
    app, limiter = create_test_app(limit=1)

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert limiter.requests == {}


def test_docs_y_openapi_son_publicos():
    app, limiter = create_test_app()

    with TestClient(app) as client:
        docs_response = client.get("/docs")
        openapi_response = client.get("/openapi.json")

    assert docs_response.status_code == 200
    assert openapi_response.status_code == 200
    assert limiter.requests == {}


def test_peticion_422_con_clave_valida_consume_limite():
    app, limiter = create_test_app(limit=1)

    with TestClient(app) as client:
        # Falta el parámetro obligatorio "q": FastAPI responde 422.
        first_response = client.get(
            "/private",
            params={"api_key": API_KEY_CORRECTA},
        )

        # La segunda petición supera el límite aunque la primera
        # haya terminado con un error de validación.
        second_response = client.get(
            "/private",
            params={"api_key": API_KEY_CORRECTA, "q": "hola"},
        )

    assert first_response.status_code == 422
    assert second_response.status_code == 429
    assert API_KEY_CORRECTA in limiter.requests



RUTAS_PROTEGIDAS_API = [
    "/ask",
    "/approve",
    "/threads/hilo-prueba",
]


@pytest.mark.parametrize("ruta", RUTAS_PROTEGIDAS_API)
def test_app_real_sin_api_key_configurada_devuelve_503(
    ruta,
    monkeypatch,
    in_memory_repo,
    fake_agent,
):
    monkeypatch.setattr(config, "API_KEY", " ")
    app = create_app(repo=in_memory_repo, agent=fake_agent)

    with TestClient(app) as client:
        response = client.get(ruta, params={"api_key": "clave-prueba"})

    assert response.status_code == 503


@pytest.mark.parametrize("ruta", RUTAS_PROTEGIDAS_API)
def test_app_real_sin_clave_devuelve_401(
    ruta,
    monkeypatch,
    in_memory_repo,
    fake_agent,
):
    monkeypatch.setattr(config, "API_KEY", "clave-prueba")
    app = create_app(repo=in_memory_repo, agent=fake_agent)

    with TestClient(app) as client:
        response = client.get(ruta)

    assert response.status_code == 401


@pytest.mark.parametrize("ruta", RUTAS_PROTEGIDAS_API)
def test_app_real_superar_limite_devuelve_429(
    ruta,
    monkeypatch,
    in_memory_repo,
    fake_agent,
):
    monkeypatch.setattr(config, "API_KEY", "clave-prueba")
    monkeypatch.setattr(config, "RATE_LIMIT_PER_MINUTE", 1)

    app = create_app(repo=in_memory_repo, agent=fake_agent)

    with TestClient(app) as client:
        primera = client.get(
            ruta,
            params={"api_key": "clave-prueba"},
        )
        segunda = client.get(
            ruta,
            params={"api_key": "clave-prueba"},
        )

    assert primera.status_code != 429
    assert segunda.status_code == 429


def test_cors_solo_origenes_listados(
    monkeypatch,
    in_memory_repo,
    fake_agent,
):
    origen_permitido = "https://frontend-prueba.com"
    origen_no_permitido = "https://otro-origen.com"
    api_key = "clave-prueba-cors"

    monkeypatch.setattr(config, "API_KEY", api_key)
    monkeypatch.setattr(config, "RATE_LIMIT_PER_MINUTE", 1)
    monkeypatch.setattr(
        config,
        "CORS_ORIGINS",
        [origen_permitido],
    )

    app = create_app(repo=in_memory_repo, agent=fake_agent)

    with TestClient(app) as client:
        # 1. El origen permitido recibe autorización CORS.
        response_permitida = client.get(
            "/health",
            headers={"Origin": origen_permitido},
        )

        assert (
            response_permitida.headers.get("access-control-allow-origin")
            == origen_permitido
        )

        # 2. El origen no incluido no recibe autorización CORS.
        response_no_permitida = client.get(
            "/health",
            headers={"Origin": origen_no_permitido},
        )

        assert (
            "access-control-allow-origin"
            not in response_no_permitida.headers
        )

        # 3. OPTIONS no necesita API key y no consume el límite.
        preflight = client.options(
            "/ask",
            headers={
                "Origin": origen_permitido,
                "Access-Control-Request-Method": "POST",
            },
        )

        assert preflight.status_code != 401

        # Con límite 1, esta petición debe poder llegar a la ruta.
        # Devolverá 404 porque el endpoint se implementará en M9.
        response_protegida = client.get(
            "/threads/hilo-prueba",
            params={"api_key": api_key},
        )

        assert response_protegida.status_code != 429
