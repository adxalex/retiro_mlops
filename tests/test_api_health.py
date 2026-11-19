from fastapi.testclient import TestClient

from api import app


client = TestClient(app)


def test_health_devuelve_status_200():
    """Comprueba que el endpoint health responde correctamente."""

    response = client.get("/health")

    assert response.status_code == 200


def test_health_devuelve_respuesta_esperada():
    """Comprueba el contenido de la respuesta del endpoint."""

    response = client.get("/health")

    assert response.json() == {
        "status": "ok",
        "message": "Retiro Agent API funcionando correctamente"
    }


def test_openapi_incluye_endpoint_health():
    """Comprueba que FastAPI registra health en su documentación."""

    response = client.get("/openapi.json")

    assert response.status_code == 200

    datos = response.json()

    assert "/health" in datos["paths"]
    assert "get" in datos["paths"]["/health"]