
from unittest.mock import Mock


def crear_plan_pendiente(
    api_client,
    fake_agent,
    thread_id="hilo-aprobacion-123",
    pregunta="Organiza una visita al Retiro",
    respuesta="He preparado un plan para tu visita.",
):
    """Crea un hilo con un plan pendiente de aprobación."""

    fake_agent.procesar_turno = Mock(
        return_value={
            "thread_id": thread_id,
            "respuesta": respuesta,
            "plan": [
                {"paso": 1, "accion": "Visitar el Palacio de Cristal"}
            ],
            "pendiente_aprobacion": True,
            "done": False,
            "traza": [],
            "error": None,
        }
    )

    response = api_client.post(
        "/ask?api_key=test-key",
        json={
            "pregunta": pregunta,
            "thread_id": thread_id,
            "auto_aprobar": False,
        },
    )

    assert response.status_code == 200
    assert response.json()["pendiente_hitl"] is True

    return response.json()


def test_approve_aprobar_plan_devuelve_done_true(
    api_client,
    fake_agent,
    in_memory_repo,
):
    thread_id = "hilo-aprobar-123"

    crear_plan_pendiente(api_client, fake_agent, thread_id)

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
        "/approve?api_key=test-key",
        json={
            "thread_id": thread_id,
            "aprobado": True,
        },
    )

    assert response.status_code == 200
    assert response.json()["done"] is True
    assert response.json()["pendiente_hitl"] is False

    fake_agent.aprobar_plan.assert_called_once_with(
        thread_id=thread_id,
        aprobado=True,
        comentario="",
    )

    assert len(in_memory_repo.turnos) == 1
    assert in_memory_repo.turnos[0].decision == "aprobado"


def test_approve_rechazar_plan_devuelve_done_false(
    api_client,
    fake_agent,
    in_memory_repo,
):
    thread_id = "hilo-rechazar-123"

    crear_plan_pendiente(api_client, fake_agent, thread_id)

    fake_agent.aprobar_plan = Mock(
        return_value={
            "thread_id": thread_id,
            "respuesta": "El plan ha sido rechazado.",
            "plan": [],
            "pendiente_aprobacion": False,
            "done": False,
            "traza": [],
            "error": None,
        }
    )

    response = api_client.post(
        "/approve?api_key=test-key",
        json={
            "thread_id": thread_id,
            "aprobado": False,
        },
    )

    assert response.status_code == 200
    assert response.json()["done"] is False
    assert response.json()["pendiente_hitl"] is False

    fake_agent.aprobar_plan.assert_called_once_with(
        thread_id=thread_id,
        aprobado=False,
        comentario="",
    )

    assert len(in_memory_repo.turnos) == 1
    assert in_memory_repo.turnos[0].decision == "rechazado"


def test_approve_guarda_el_comentario(
    api_client,
    fake_agent,
    in_memory_repo,
):
    thread_id = "hilo-comentario-123"
    comentario = "Prefiero cambiar el orden de las visitas."

    crear_plan_pendiente(api_client, fake_agent, thread_id)

    fake_agent.aprobar_plan = Mock(
        return_value={
            "thread_id": thread_id,
            "respuesta": "Tu plan ha sido aprobado.",
            "plan": [],
            "pendiente_aprobacion": False,
            "done": True,
            "traza": [],
            "error": None,
        }
    )

    response = api_client.post(
        "/approve?api_key=test-key",
        json={
            "thread_id": thread_id,
            "aprobado": True,
            "comentario": comentario,
        },
    )

    assert response.status_code == 200

    fake_agent.aprobar_plan.assert_called_once_with(
        thread_id=thread_id,
        aprobado=True,
        comentario=comentario,
    )

    assert len(in_memory_repo.turnos) == 1
    assert in_memory_repo.turnos[0].comment == comentario


def test_approve_rechazo_guarda_respuesta_original_del_ask(
    api_client,
    fake_agent,
    in_memory_repo,
):
    thread_id = "hilo-respuesta-original-123"
    respuesta_original = "He preparado una ruta por el Retiro."

    crear_plan_pendiente(
        api_client,
        fake_agent,
        thread_id=thread_id,
        respuesta=respuesta_original,
    )

    fake_agent.aprobar_plan = Mock(
        return_value={
            "thread_id": thread_id,
            "respuesta": "El plan ha sido rechazado.",
            "plan": [],
            "pendiente_aprobacion": False,
            "done": False,
            "traza": [],
            "error": None,
        }
    )

    response = api_client.post(
        "/approve?api_key=test-key",
        json={
            "thread_id": thread_id,
            "aprobado": False,
            "comentario": "No me convence esta ruta.",
        },
    )

    assert response.status_code == 200
    assert len(in_memory_repo.turnos) == 1

    turno = in_memory_repo.turnos[0]

    assert turno.answer == respuesta_original
    assert turno.decision == "rechazado"
    assert turno.comment == "No me convence esta ruta."



def test_approve_hilo_desconocido_devuelve_409(api_client):
    response = api_client.post(
        "/approve?api_key=test-key",
        json={
            "thread_id": "hilo-desconocido-123",
            "aprobado": True,
        },
    )

    assert response.status_code == 409


def test_approve_hilo_sin_plan_pendiente_devuelve_409(
    api_client,
    fake_agent,
):
    response_ask = api_client.post(
        "/ask?api_key=test-key",
        json={
            "pregunta": "¿Dónde está el Palacio de Cristal?",
            "thread_id": "hilo-sin-pendiente-123",
        },
    )

    assert response_ask.status_code == 200

    response = api_client.post(
        "/approve?api_key=test-key",
        json={
            "thread_id": "hilo-sin-pendiente-123",
            "aprobado": True,
        },
    )

    assert response.status_code == 409


def test_approve_comentario_superior_a_500_caracteres_devuelve_422(
    api_client,
):
    response = api_client.post(
        "/approve?api_key=test-key",
        json={
            "thread_id": "hilo-comentario-largo-123",
            "aprobado": True,
            "comentario": "a" * 501,
        },
    )

    assert response.status_code == 422


def test_approve_peticion_en_curso_devuelve_409(
    api_client,
    fake_agent,
):
    thread_id = "hilo-en-curso-123"

    crear_plan_pendiente(api_client, fake_agent, thread_id)

    # Simulamos que el agente sigue procesando una petición en este hilo.
    api_client.app.state.in_flight_threads.add(thread_id)

    response = api_client.post(
        "/approve?api_key=test-key",
        json={
            "thread_id": thread_id,
            "aprobado": True,
        },
    )

    assert response.status_code == 409
