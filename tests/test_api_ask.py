from concurrent.futures import ThreadPoolExecutor
from threading import Event
from time import monotonic, sleep
from unittest.mock import Mock

from fastapi.testclient import TestClient


def test_ask_respuesta_correcta(api_client, in_memory_repo):
    response = api_client.post(
        "/ask?api_key=test-key",
        json={"pregunta": "¿Qué puedo visitar en el Retiro?"},
    )

    assert response.status_code == 200

    data = response.json()

    assert data["respuesta"] == "Respuesta de prueba"
    assert data["plan"] == []
    assert data["thread_id"]
    assert data["done"] is True
    assert data["pendiente_hitl"] is False
    assert data["error"] is None

    assert len(in_memory_repo.turnos) == 1


def test_ask_genera_thread_id_automaticamente(api_client):
    response = api_client.post(
        "/ask?api_key=test-key",
        json={"pregunta": "¿Qué puedo visitar?"},
    )

    assert response.status_code == 200
    assert response.json()["thread_id"]


def test_ask_pregunta_vacia(api_client):
    response = api_client.post(
        "/ask?api_key=test-key",
        json={"pregunta": ""},
    )

    assert response.status_code == 422


def test_ask_pregunta_solo_espacios(api_client):
    response = api_client.post(
        "/ask?api_key=test-key",
        json={"pregunta": "     "},
    )

    assert response.status_code == 422


def test_ask_pregunta_supera_2000_caracteres(api_client):
    response = api_client.post(
        "/ask?api_key=test-key",
        json={"pregunta": "a" * 2001},
    )

    assert response.status_code == 422


def test_ask_thread_id_invalido(api_client):
    response = api_client.post(
        "/ask?api_key=test-key",
        json={
            "pregunta": "¿Qué puedo visitar?",
            "thread_id": "hilo no valido",
        },
    )

    assert response.status_code == 422


def test_ask_error_agente_no_guarda_turno(
    api_client,
    in_memory_repo,
    fake_agent,
):
    fake_agent.procesar_turno = Mock(
        side_effect=RuntimeError("Error interno secreto")
    )

    with TestClient(
        api_client.app,
        raise_server_exceptions=False,
    ) as client:
        response = client.post(
            "/ask?api_key=test-key",
            json={"pregunta": "¿Qué puedo visitar?"},
        )

    assert response.status_code == 500
    assert response.json() == {
        "detail": "Error interno del servidor"
    }
    assert "Error interno secreto" not in response.text
    assert len(in_memory_repo.turnos) == 0


def test_ask_sin_plan_guarda_decision_none(
    api_client,
    in_memory_repo,
):
    response = api_client.post(
        "/ask?api_key=test-key",
        json={"pregunta": "¿Qué puedo visitar?"},
    )

    assert response.status_code == 200
    assert len(in_memory_repo.turnos) == 1
    assert in_memory_repo.turnos[0].decision is None


def test_ask_plan_pendiente_no_guarda_turno(
    api_client,
    in_memory_repo,
    fake_agent,
):
    fake_agent.procesar_turno = Mock(
        return_value={
            "thread_id": "hilo-pendiente-123",
            "respuesta": "He preparado un plan para tu visita.",
            "plan": [{"paso": 1, "accion": "Visitar el Palacio de Cristal"}],
            "pendiente_aprobacion": True,
            "done": False,
            "traza": [],
            "error": None,
        }
    )

    response = api_client.post(
        "/ask?api_key=test-key",
        json={
            "pregunta": "Organiza una visita al Retiro",
            "thread_id": "hilo-pendiente-123",
            "auto_aprobar": False,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["pendiente_hitl"] is True
    assert data["done"] is False
    assert data["thread_id"] == "hilo-pendiente-123"
    assert len(in_memory_repo.turnos) == 0


def test_ask_hilo_con_plan_pendiente_devuelve_409(
    api_client,
    fake_agent,
):
    fake_agent.procesar_turno = Mock(
        return_value={
            "thread_id": "hilo-pendiente-123",
            "respuesta": "Hay un plan pendiente.",
            "plan": [{"paso": 1, "accion": "Visitar el Retiro"}],
            "pendiente_aprobacion": True,
            "done": False,
            "traza": [],
            "error": None,
        }
    )

    primera_respuesta = api_client.post(
        "/ask?api_key=test-key",
        json={
            "pregunta": "Organiza una visita",
            "thread_id": "hilo-pendiente-123",
            "auto_aprobar": False,
        },
    )

    assert primera_respuesta.status_code == 200

    segunda_respuesta = api_client.post(
        "/ask?api_key=test-key",
        json={
            "pregunta": "Añade otro lugar a la visita",
            "thread_id": "hilo-pendiente-123",
            "auto_aprobar": False,
        },
    )

    assert segunda_respuesta.status_code == 409
    assert fake_agent.procesar_turno.call_count == 1

 
def test_ask_auto_aprueba_plan_por_defecto(
    api_client,
    in_memory_repo,
    fake_agent,
):
    thread_id = "hilo-auto-aprobacion-123"

    fake_agent.procesar_turno = Mock(
        return_value={
            "thread_id": thread_id,
            "respuesta": "He preparado un plan para tu visita.",
            "plan": [
                {"paso": 1, "accion": "Visitar el Palacio de Cristal"}
            ],
            "pendiente_aprobacion": True,
            "done": False,
            "traza": [],
            "error": None,
        }
    )

    fake_agent.aprobar_plan = Mock(
        return_value={
            "thread_id": thread_id,
            "respuesta": "Tu plan ha sido aprobado.",
            "plan": [
                {"paso": 1, "accion": "Visitar el Palacio de Cristal"}
            ],
            "pendiente_aprobacion": False,
            "done": True,
            "traza": [],
            "error": None,
        }
    )

    response = api_client.post(
        "/ask?api_key=test-key",
        json={
            "pregunta": "Organiza una visita al Retiro",
            "thread_id": thread_id,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["done"] is True
    assert data["pendiente_hitl"] is False
    assert data["thread_id"] == thread_id

    fake_agent.aprobar_plan.assert_called_once_with(
        thread_id=thread_id,
        aprobado=True,
        comentario="",
    )

    assert len(in_memory_repo.turnos) == 1
    turno = in_memory_repo.turnos[0]

    assert turno.decision == "aprobado"
    assert turno.comment == ""



def test_ask_sin_plan_no_activa_auto_aprobacion(
    api_client,
    in_memory_repo,
    fake_agent,
):
    fake_agent.aprobar_plan = Mock()

    response = api_client.post(
        "/ask?api_key=test-key",
        json={
            "pregunta": "¿Dónde está el Palacio de Cristal?",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["done"] is True
    assert data["pendiente_hitl"] is False

    fake_agent.aprobar_plan.assert_not_called()

    assert len(in_memory_repo.turnos) == 1
    assert in_memory_repo.turnos[0].decision is None

def test_ask_timeout_devuelve_504_y_no_guarda_turno(
    api_client,
    in_memory_repo,
    fake_agent,
    monkeypatch,
):
    import config

    monkeypatch.setattr(config, "ASK_TIMEOUT_SECONDS", 0.1)

    agente_iniciado = Event()
    liberar_agente = Event()

    def agente_bloqueado(texto, thread_id, imagen=None):
        agente_iniciado.set()
        liberar_agente.wait(timeout=3)

        return {
            "thread_id": thread_id,
            "respuesta": "Respuesta de prueba",
            "plan": [],
            "pendiente_aprobacion": False,
            "done": True,
            "traza": [],
            "error": None,
        }

    fake_agent.procesar_turno = Mock(side_effect=agente_bloqueado)

    try:
        response = api_client.post(
            "/ask?api_key=test-key",
            json={
                "pregunta": "¿Qué puedo visitar?",
                "thread_id": "hilo-timeout-123",
            },
        )

        assert response.status_code == 504
        assert agente_iniciado.is_set()
        assert len(in_memory_repo.turnos) == 0

    finally:
        liberar_agente.set()


def test_ask_segunda_peticion_mismo_hilo_devuelve_409(
    api_client,
    in_memory_repo,
    fake_agent,
    monkeypatch,
):
    import config

    monkeypatch.setattr(config, "ASK_TIMEOUT_SECONDS", 3)

    agente_iniciado = Event()
    liberar_agente = Event()

    def agente_bloqueado(texto, thread_id, imagen=None):
        agente_iniciado.set()
        liberar_agente.wait(timeout=3)

        return {
            "thread_id": thread_id,
            "respuesta": "Respuesta de prueba",
            "plan": [],
            "pendiente_aprobacion": False,
            "done": True,
            "traza": [],
            "error": None,
        }

    fake_agent.procesar_turno = Mock(side_effect=agente_bloqueado)

    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            primera_peticion = executor.submit(
                api_client.post,
                "/ask?api_key=test-key",
                json={
                    "pregunta": "Organiza una visita",
                    "thread_id": "hilo-concurrente-123",
                },
            )

            assert agente_iniciado.wait(timeout=2)

            segunda_peticion = api_client.post(
                "/ask?api_key=test-key",
                json={
                    "pregunta": "Añade otro lugar",
                    "thread_id": "hilo-concurrente-123",
                },
            )

            assert segunda_peticion.status_code == 409
            fake_agent.procesar_turno.assert_called_once()

            liberar_agente.set()

            primera_respuesta = primera_peticion.result(timeout=3)

            assert primera_respuesta.status_code == 200

    finally:
        liberar_agente.set()


def test_ask_reserva_se_libera_cuando_agente_termina(
    api_client,
    in_memory_repo,
    fake_agent,
    monkeypatch,
):
    import config

    monkeypatch.setattr(config, "ASK_TIMEOUT_SECONDS", 0.1)

    agente_iniciado = Event()
    liberar_agente = Event()
    agente_terminado = Event()

    def agente_controlado(texto, thread_id, imagen=None):
        if fake_agent.procesar_turno.call_count == 1:
            agente_iniciado.set()
            liberar_agente.wait(timeout=3)
            agente_terminado.set()

        return {
            "thread_id": thread_id,
            "respuesta": "Respuesta de prueba",
            "plan": [],
            "pendiente_aprobacion": False,
            "done": True,
            "traza": [],
            "error": None,
        }

    fake_agent.procesar_turno = Mock(side_effect=agente_controlado)

    try:
        primera_respuesta = api_client.post(
            "/ask?api_key=test-key",
            json={
                "pregunta": "Organiza una visita",
                "thread_id": "hilo-liberacion-123",
            },
        )

        assert primera_respuesta.status_code == 504
        assert agente_iniciado.is_set()
        assert len(in_memory_repo.turnos) == 0

        # El agente sigue trabajando: el hilo debe continuar reservado.
        segunda_respuesta = api_client.post(
            "/ask?api_key=test-key",
            json={
                "pregunta": "Añade otro lugar",
                "thread_id": "hilo-liberacion-123",
            },
        )

        assert segunda_respuesta.status_code == 409
        assert fake_agent.procesar_turno.call_count == 1

        # Permitimos que el agente termine realmente.
        liberar_agente.set()
        assert agente_terminado.wait(timeout=2)

        # Esperamos a que se libere la reserva.
        limite = monotonic() + 2
        tercera_respuesta = None

        while monotonic() < limite:
            tercera_respuesta = api_client.post(
                "/ask?api_key=test-key",
                json={
                    "pregunta": "Organiza una nueva visita",
                    "thread_id": "hilo-liberacion-123",
                },
            )

            if tercera_respuesta.status_code != 409:
                break

            sleep(0.01)

        assert tercera_respuesta is not None
        assert tercera_respuesta.status_code == 200
        assert fake_agent.procesar_turno.call_count == 2
        assert len(in_memory_repo.turnos) == 1

    finally:
        liberar_agente.set()