
from unittest.mock import Mock


def test_historial_devuelve_mensajes_en_orden_cronologico(
    api_client,
    in_memory_repo,
):
    thread_id = "hilo-historial-123"

    in_memory_repo.save(
        thread_id=thread_id,
        question="¿Dónde está el Palacio de Cristal?",
        answer="Está en el Parque del Retiro.",
        decision=None,
        comment=None,
    )

    in_memory_repo.save(
        thread_id=thread_id,
        question="¿Cuánto se tarda en llegar?",
        answer="Aproximadamente diez minutos.",
        decision="aprobado",
        comment="De acuerdo.",
    )

    response = api_client.get(
        f"/threads/{thread_id}/messages?api_key=test-key"
    )

    assert response.status_code == 200

    mensajes = response.json()

    assert len(mensajes) == 4
    assert [mensaje["role"] for mensaje in mensajes] == [
        "user",
        "assistant",
        "user",
        "assistant",
    ]

    assert mensajes[0]["content"] == "¿Dónde está el Palacio de Cristal?"
    assert mensajes[1]["content"] == "Está en el Parque del Retiro."
    assert mensajes[2]["content"] == "¿Cuánto se tarda en llegar?"
    assert mensajes[3]["content"] == "Aproximadamente diez minutos."

    fechas = [mensaje["created_at"] for mensaje in mensajes]
    assert fechas == sorted(fechas)


def test_historial_decision_y_comentario_solo_en_asistente(
    api_client,
    in_memory_repo,
):
    thread_id = "hilo-decision-123"

    in_memory_repo.save(
        thread_id=thread_id,
        question="Organiza una visita",
        answer="He preparado una ruta.",
        decision="rechazado",
        comment="Prefiero otra ruta.",
    )

    response = api_client.get(
        f"/threads/{thread_id}/messages?api_key=test-key"
    )

    assert response.status_code == 200

    mensajes = response.json()

    assert len(mensajes) == 2

    mensaje_usuario = mensajes[0]
    mensaje_asistente = mensajes[1]

    assert mensaje_usuario["role"] == "user"
    assert mensaje_usuario["decision"] is None
    assert mensaje_usuario["comentario"] is None

    assert mensaje_asistente["role"] == "assistant"
    assert mensaje_asistente["decision"] == "rechazado"
    assert mensaje_asistente["comentario"] == "Prefiero otra ruta."


def test_historial_hilo_sin_turnos_devuelve_404(api_client):
    response = api_client.get(
        "/threads/hilo-vacio-123/messages?api_key=test-key"
    )

    assert response.status_code == 404


def test_historial_plan_pendiente_sin_turnos_cerrados_devuelve_404(
    api_client,
    fake_agent,
):
    thread_id = "hilo-pendiente-historial-123"

    fake_agent.procesar_turno = Mock(
        return_value={
            "thread_id": thread_id,
            "respuesta": "He preparado un plan.",
            "plan": [{"paso": 1, "accion": "Visitar el Retiro"}],
            "pendiente_aprobacion": True,
            "done": False,
            "traza": [],
            "error": None,
        }
    )

    response_ask = api_client.post(
        "/ask?api_key=test-key",
        json={
            "pregunta": "Organiza una visita",
            "thread_id": thread_id,
            "auto_aprobar": False,
        },
    )

    assert response_ask.status_code == 200
    assert response_ask.json()["pendiente_hitl"] is True

    response_historial = api_client.get(
        f"/threads/{thread_id}/messages?api_key=test-key"
    )

    assert response_historial.status_code == 404


def test_historial_thread_id_invalido_devuelve_422(api_client):
    response = api_client.get(
        "/threads/hilo%20invalido/messages?api_key=test-key"
    )

    assert response.status_code == 422
