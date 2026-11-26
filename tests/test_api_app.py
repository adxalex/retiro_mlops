
from fastapi.testclient import TestClient

from api import create_app


def test_health_repositorio_sano(api_client):
    response = api_client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "storage": "postgres",
        "db": "ok",
    }


def test_health_repositorio_roto(api_client_roto):
    response = api_client_roto.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "storage": "postgres",
        "db": "error",
    }


def test_docs_es_publico(api_client):
    response = api_client.get("/docs")

    assert response.status_code == 200


def test_openapi_es_publico(api_client):
    response = api_client.get("/openapi.json")

    assert response.status_code == 200
    assert "openapi" in response.json()


def test_redoc_no_existe(api_client):
    response = api_client.get("/redoc")

    assert response.status_code == 404



from fastapi import Query
from fastapi.testclient import TestClient


def test_error_422_en_espanol_sin_mostrar_valores(api_client):
    def endpoint(valor: int = Query(...)):
        return {"valor": valor}

    api_client.app.add_api_route(
        "/_test/validation",
        endpoint,
        methods=["GET"],
    )

    response = api_client.get("/_test/validation?valor=SECRETO")

    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)
    assert "SECRETO" not in response.text
    assert response.json()["detail"] == "Solicitud no válida"


def test_error_404_en_espanol(api_client):
    response = api_client.get("/ruta-que-no-existe")

    assert response.status_code == 404
    assert isinstance(response.json()["detail"], str)
    assert response.json()["detail"] == "Recurso no encontrado"


def test_error_405_en_espanol(api_client):
    response = api_client.post("/health")

    assert response.status_code == 405
    assert isinstance(response.json()["detail"], str)
    assert response.json()["detail"] == "Método no permitido"


def test_error_500_generico(api_client):
    def endpoint():
        raise RuntimeError("Este detalle no debe mostrarse")

    api_client.app.add_api_route(
        "/_test/error",
        endpoint,
        methods=["GET"],
    )

    with TestClient(
        api_client.app,
        raise_server_exceptions=False,
    ) as client:
        response = client.get("/_test/error")

    assert response.status_code == 500
    assert response.json() == {
        "detail": "Error interno del servidor"
    }
    assert "Este detalle no debe mostrarse" not in response.text
