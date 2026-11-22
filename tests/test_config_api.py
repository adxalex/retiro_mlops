"""Configuración de la API HTTP: valores por defecto y lectura del entorno."""

import importlib

import dotenv
import pytest

import config

NOMBRES_ENTORNO = (
    "API_KEY",
    "DATABASE_URL",
    "RATE_LIMIT_PER_MINUTE",
    "ASK_TIMEOUT_SECONDS",
    "CORS_ORIGINS",
)


@pytest.fixture
def recargar_config(monkeypatch):
    """Recarga config con un entorno controlado y sin leer el .env local."""
    monkeypatch.setattr(dotenv, "load_dotenv", lambda *a, **k: False)

    def _recargar(**entorno):
        for nombre in NOMBRES_ENTORNO:
            monkeypatch.delenv(nombre, raising=False)
        for nombre, valor in entorno.items():
            monkeypatch.setenv(nombre, valor)
        return importlib.reload(config)

    yield _recargar

    # Restaura entorno y load_dotenv reales antes de dejar config como estaba.
    monkeypatch.undo()
    importlib.reload(config)


def test_valores_por_defecto(recargar_config):
    cfg = recargar_config()
    assert cfg.API_KEY == ""
    assert cfg.DATABASE_URL == ""
    assert cfg.RATE_LIMIT_PER_MINUTE == 30
    assert cfg.ASK_TIMEOUT_SECONDS == 60
    assert cfg.CORS_ORIGINS == []


def test_constantes_fijas(recargar_config):
    cfg = recargar_config()
    assert cfg.PREGUNTA_MAX_CHARS == 2000
    assert cfg.COMENTARIO_MAX_CHARS == 500
    assert cfg.THREAD_ID_MAX_CHARS == 64
    assert cfg.DB_CONNECT_TIMEOUT_SECONDS > 0
    assert cfg.RUTAS_PROTEGIDAS == ("/ask", "/approve", "/threads/")


def test_lee_el_entorno(recargar_config):
    cfg = recargar_config(
        API_KEY="clave-de-prueba",
        DATABASE_URL="postgres://usuario@host/bd",
        RATE_LIMIT_PER_MINUTE="5",
        ASK_TIMEOUT_SECONDS="0.5",
    )
    assert cfg.API_KEY == "clave-de-prueba"
    assert cfg.DATABASE_URL == "postgres://usuario@host/bd"
    assert cfg.RATE_LIMIT_PER_MINUTE == 5
    assert cfg.ASK_TIMEOUT_SECONDS == 0.5


def test_variables_vacias_usan_el_valor_por_defecto(recargar_config):
    # Un .env copiado de .env.example deja los nombres con valor vacío.
    cfg = recargar_config(
        RATE_LIMIT_PER_MINUTE="",
        ASK_TIMEOUT_SECONDS="",
        API_KEY="",
        DATABASE_URL="",
        CORS_ORIGINS="",
    )
    assert cfg.RATE_LIMIT_PER_MINUTE == 30
    assert cfg.ASK_TIMEOUT_SECONDS == 60
    assert cfg.API_KEY == ""
    assert cfg.DATABASE_URL == ""
    assert cfg.CORS_ORIGINS == []


def test_cors_origins_separados_por_comas_y_sin_espacios(recargar_config):
    cfg = recargar_config(
        CORS_ORIGINS="https://front.example.com , http://localhost:8501,,"
    )
    assert cfg.CORS_ORIGINS == [
        "https://front.example.com",
        "http://localhost:8501",
    ]


@pytest.mark.parametrize("valor", ["", "   ", " , ,"])
def test_cors_origins_vacio_no_permite_ninguno(recargar_config, valor):
    cfg = recargar_config(CORS_ORIGINS=valor)
    assert cfg.CORS_ORIGINS == []
