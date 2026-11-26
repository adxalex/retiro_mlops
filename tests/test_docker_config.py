"""Configuración estática de Docker y despliegue en Render."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def leer_archivo(relativo):
    ruta = ROOT / relativo
    assert ruta.is_file(), f"Falta el archivo {relativo}"
    return ruta.read_text(encoding="utf-8")


def test_dockerfile_usa_python_310():
    dockerfile = leer_archivo("Dockerfile")
    assert "FROM python:3.10-slim" in dockerfile


def test_instala_requirements():
    dockerfile = leer_archivo("Dockerfile")
    assert "COPY requirements.txt" in dockerfile
    assert "pip install --no-cache-dir -r requirements.txt" in dockerfile


def test_uvicorn_inicia_api_app():
    dockerfile = leer_archivo("Dockerfile")
    assert "uvicorn" in dockerfile
    assert "api:app" in dockerfile


def test_host_es_todos_los_interfaces():
    dockerfile = leer_archivo("Dockerfile")
    assert "--host 0.0.0.0" in dockerfile or "--host=0.0.0.0" in dockerfile


def test_puerto_render_y_fallback():
    dockerfile = leer_archivo("Dockerfile")
    assert "PORT" in dockerfile
    assert "8000" in dockerfile


def test_un_solo_worker():
    dockerfile = leer_archivo("Dockerfile")
    assert "--workers 1" in dockerfile or "--workers=1" in dockerfile


def test_no_access_log():
    dockerfile = leer_archivo("Dockerfile")
    assert "--no-access-log" in dockerfile


def test_dockerignore_excluye_archivos_locales():
    dockerignore = leer_archivo(".dockerignore")
    for patron in (".git", "venv/", ".venv/", "__pycache__", "output/", "chroma/"):
        assert patron in dockerignore


def test_dockerignore_excluye_secretos():
    dockerignore = leer_archivo(".dockerignore")
    assert ".env" in dockerignore
    assert "!.env.example" in dockerignore


def test_documenta_variables_de_entorno():
    readme = leer_archivo("README.md")
    for variable in (
        "API_KEY",
        "DATABASE_URL",
        "GEMINI_API_KEY",
        "AEMET_API_KEY",
        "CORS_ORIGINS",
        "PORT",
    ):
        assert variable in readme
    assert "8000" in readme
