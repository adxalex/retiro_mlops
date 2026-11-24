
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from schemas import (
    AskRequest,
    ApproveRequest,
    AskResponse,
    MessageResponse,
)


# ---------------------------------------------------------
# ASK REQUEST
# ---------------------------------------------------------

def test_pregunta_se_recorta():
    request = AskRequest(pregunta="  ¿Qué horario tiene el Retiro?  ")

    assert request.pregunta == "¿Qué horario tiene el Retiro?"


def test_pregunta_no_puede_estar_vacia():
    with pytest.raises(ValidationError):
        AskRequest(pregunta="   ")


def test_pregunta_admite_2000_caracteres():
    request = AskRequest(pregunta="a" * 2000)

    assert len(request.pregunta) == 2000


def test_pregunta_no_admite_mas_de_2000_caracteres():
    with pytest.raises(ValidationError):
        AskRequest(pregunta="a" * 2001)


def test_thread_id_es_opcional_en_ask():
    request = AskRequest(pregunta="¿Cuándo abre el parque?")

    assert request.thread_id is None


def test_thread_id_admite_hasta_64_caracteres():
    request = AskRequest(
        pregunta="¿Cuándo abre el parque?",
        thread_id="a" * 64,
    )

    assert len(request.thread_id) == 64


def test_thread_id_no_admite_mas_de_64_caracteres():
    with pytest.raises(ValidationError):
        AskRequest(
            pregunta="¿Cuándo abre el parque?",
            thread_id="a" * 65,
        )


def test_thread_id_no_admite_espacios():
    with pytest.raises(ValidationError):
        AskRequest(
            pregunta="¿Cuándo abre el parque?",
            thread_id="mi hilo",
        )


def test_auto_aprobar_por_defecto_es_true():
    request = AskRequest(pregunta="¿Cuándo abre el parque?")

    assert request.auto_aprobar is True


# ---------------------------------------------------------
# APPROVE REQUEST
# ---------------------------------------------------------

def test_comentario_admite_hasta_500_caracteres():
    request = ApproveRequest(
        thread_id="hilo-123",
        aprobado=True,
        comentario="a" * 500,
    )

    assert len(request.comentario) == 500


def test_comentario_no_admite_mas_de_500_caracteres():
    with pytest.raises(ValidationError):
        ApproveRequest(
            thread_id="hilo-123",
            aprobado=True,
            comentario="a" * 501,
        )


def test_thread_id_de_approve_no_admite_espacios():
    with pytest.raises(ValidationError):
        ApproveRequest(
            thread_id="mi hilo",
            aprobado=True,
        )


# ---------------------------------------------------------
# ASK RESPONSE
# ---------------------------------------------------------

def test_respuesta_admite_error_none():
    response = AskResponse(
        respuesta="El parque abre a las 6:00.",
        plan=[],
        thread_id="hilo-123",
        done=True,
        pendiente_hitl=False,
    )

    assert response.error is None


# ---------------------------------------------------------
# MESSAGE RESPONSE
# ---------------------------------------------------------

def test_mensaje_incluye_campos_del_historial():
    fecha = datetime.now(timezone.utc)

    message = MessageResponse(
        role="assistant",
        content="El parque abre a las 6:00.",
        created_at=fecha,
        decision="aprobado",
        comentario="De acuerdo.",
    )

    assert message.role == "assistant"
    assert message.content == "El parque abre a las 6:00."
    assert message.created_at == fecha
    assert message.decision == "aprobado"
    assert message.comentario == "De acuerdo."
