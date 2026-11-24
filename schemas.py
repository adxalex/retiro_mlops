
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class AskRequest(BaseModel):
    """Datos necesarios para enviar una pregunta al agente."""

    pregunta: str = Field(min_length=1, max_length=2000)
    thread_id: str | None = Field(default=None, min_length=1, max_length=64)
    auto_aprobar: bool = True

    @field_validator("pregunta", mode="before")
    @classmethod
    def limpiar_pregunta(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("thread_id")
    @classmethod
    def validar_thread_id(cls, value: str | None) -> str | None:
        if value is not None and any(char.isspace() for char in value):
            raise ValueError("thread_id no puede contener espacios")
        return value


class ApproveRequest(BaseModel):
    """Datos necesarios para aprobar o rechazar un plan."""

    thread_id: str = Field(min_length=1, max_length=64)
    aprobado: bool
    comentario: str | None = Field(default=None, max_length=500)

    @field_validator("thread_id")
    @classmethod
    def validar_thread_id(cls, value: str) -> str:
        if any(char.isspace() for char in value):
            raise ValueError("thread_id no puede contener espacios")
        return value


class AskResponse(BaseModel):
    """Respuesta devuelta por el endpoint /ask."""

    respuesta: str
    plan: list[dict[str, Any]]
    thread_id: str
    done: bool
    pendiente_hitl: bool
    error: str | None = None


class MessageResponse(BaseModel):
    """Mensaje individual del historial de una conversación."""

    role: str
    content: str
    created_at: datetime
    decision: str | None = None
    comentario: str | None = None
