# Plan técnico — Spec 008

> Basado en `spec.md` (estado: Borrador). No modifica el código de negocio ni el contrato HTTP.

## Archivos afectados
| Archivo | Crear / Modificar | Qué cambia | RF |
|---|---|---|---|
| `Dockerfile` | Crear | Imagen Python, instalación de `requirements.txt`, copia del código y arranque Uvicorn con un único proceso, host y puerto dinámico | RF-1 a RF-7 |
| `.dockerignore` | Crear | Excluye Git, entornos locales, cachés, resultados locales, tests, documentación, archivos temporales y secretos del contexto Docker | RF-8, RF-9 |
| `README.md` | Modificar | Documenta construcción, ejecución local, puerto predeterminado y variables de Render sin incluir valores reales | RF-10 |
| `render.yaml` | Crear opcional en implementación | Declara el servicio Docker sin fijar manualmente `PORT`; Render proporciona esa variable | RF-5, RF-10 |
| `tests/test_docker_config.py` | Crear | Comprueba de forma estática el Dockerfile y `.dockerignore` sin construir ni llamar a APIs | RF-1 a RF-10 |

## Contrato
No cambian `procesar_turno`, `aprobar_plan`, las rutas HTTP ni los esquemas Pydantic. El único contrato nuevo es operativo:

```text
Entrada de build:
  docker build -t retiro-api .

Entrada de run local:
  docker run --rm -p 8080:8080 ^
    -e PORT=8080 ^
    -e API_KEY=<valor-del-entorno> ^
    -e DATABASE_URL=<valor-del-entorno> ^
    -e GEMINI_API_KEY=<valor-del-entorno> ^
    retiro-api

Comando efectivo dentro del contenedor:
  python -m uvicorn api:app --host 0.0.0.0 --port <PORT o 8000> --workers 1 --no-access-log

Salida:
  FastAPI disponible en http://0.0.0.0:<puerto>
```

El puerto predeterminado documentado será `8000` cuando `PORT` no esté definido. Las credenciales se entregan mediante variables de entorno del proceso o del panel de Render; nunca como argumentos persistidos en la imagen ni dentro de `.env`.

## Lógica clave
```text
Dockerfile:
  partir de python:3.10-slim
  establecer directorio de trabajo /app
  copiar requirements.txt
  ejecutar pip install --no-cache-dir -r requirements.txt
  copiar el código versionado necesario: config.py, src/, data/, scripts/
  incorporar api.py al contexto sin que Docker dependa de su existencia durante M5
  no copiar chroma/ ni descargar índices automáticamente
  declarar ENV PORT=8000
  exponer el puerto predeterminado
  ejecutar uvicorn con:
    api:app
    host 0.0.0.0
    port desde PORT, con 8000 como fallback
    workers=1
    no-access-log

Arranque de shell:
  puerto = variable PORT si es no vacía; si no, 8000
  exec uvicorn api:app --host 0.0.0.0 --port "$puerto" --workers 1 --no-access-log
```

El `Dockerfile` no debe leer ni copiar `.env`, ni ejecutar código de negocio distinto de la importación de `api:app`.

Mientras `api.py` no esté integrado, el build puede completarse con el contexto disponible y el arranque se pospone a M5. Esta fase prepara la imagen sin modificar ni completar el servicio HTTP.

## Decisiones técnicas
| Decisión | Alternativa descartada | Por qué |
|---|---|---|
| Imagen base `python:3.10-slim` | `python:3.14-slim` o imagen completa | El mínimo admitido por la constitución es Python 3.10 y la variante slim reduce tamaño sin cambiar el stack. |
| Arranque mediante una instrucción shell que lee `PORT` | CMD fijo o múltiples workers | Permite el puerto de Render y conserva un único proceso con puerto predeterminado `8000`. |
| Uvicorn con `--workers 1` y sin `--no-access-log` como opción desacoplada | Multiworker, gunicorn o acceso de Uvicorn habilitado | Cumple una sola réplica/proceso y evita registrar la `api_key` en la query. |
| `.dockerignore` explícito y exclusión de `.env*` salvo `.env.example` | Copiar todo el contexto o confiar solo en `.gitignore` | `.gitignore` no controla automáticamente Docker y el entorno puede tener archivos locales. |
| Variables de entorno sin valores en la imagen | ARG/ENV con credenciales o copia de `.env` | Los secretos quedan fuera de las capas y pueden rotarse en el panel de Render. |
| README como documentación principal de Docker y Render | Solo `render.yaml` sin documentación | El README explica build/run a desarrolladores y el archivo opcional facilita la configuración de Render. |
| `PORT` se deja a cargo de Render, con fallback `8000` en el contenedor | Declarar `PORT` manualmente en `render.yaml` | Render aporta el puerto en producción y el fallback mantiene la ejecución local predecible. |
| `--workers 1` solo garantiza un proceso Uvicorn por contenedor | Suponer que impide las réplicas de Render | El escalado horizontal debe permanecer deshabilitado mientras el checkpoint y los planes pendientes estén en memoria. |
| Sin Docker healthcheck adicional | Añadir `HEALTHCHECK` a `/health` | La spec deja abierto este punto y el endpoint `/health` todavía depende de M5; no se añade una modificación fuera del alcance. |
| Tests estáticos de configuración más Docker build manual | Tests que ejecuten un contenedor como parte de pytest | Evita requerir Docker y APIs externas en pytest; el build real se valida manualmente cuando Docker esté disponible. |

## Estrategia de tests
**Dobles y aislamiento**:
- Los tests Docker no llaman a Gemini, AEMET, PostgreSQL ni Internet.
- Las comprobaciones staticas leen el `Dockerfile` y `.dockerignore` como texto.
- El build real usa el código local y paquetes de `requirements.txt`; no requiere claves si solo se construye la imagen.
- El arranque real debe sustituir el agente y la base de datos por dobles solo si se ejecutan tests contra `api:app`; Docker no incorpora esas dobles en la imagen.

**Automático**:
- `tests/test_docker_config.py::test_dockerfile_usa_python_310` cubre RF-1 y compatibilidad.
- `tests/test_docker_config.py::test_instala_requirements` cubre RF-2.
- `tests/test_docker_config.py::test_uvicorn_inicia_api_app` cubre RF-3.
- `tests/test_docker_config.py::test_host_es_todos_los_interfaces` cubre RF-4.
- `tests/test_docker_config.py::test_puerto_render_y_fallback` cubre RF-5 y el caso límite de `PORT` ausente.
- `tests/test_docker_config.py::test_un_solo_worker` cubre RF-6.
- `tests/test_docker_config.py::test_no_access_log` cubre RF-7.
- `tests/test_docker_config.py::test_dockerignore_excluye_archivos_locales` cubre RF-8.
- `tests/test_docker_config.py::test_dockerignore_excluye_secretos` cubre RF-9.
- `tests/test_docker_config.py::test_documenta_variables_de_entorno` cubre RF-10.

**Solo a mano**:
- Construcción real: `docker build -t retiro-api .`.
- Instalación de dependencias: verificar que el build termina y que no aparecen dependencias incompatibles.
- Arranque real con `PORT=8080`: comprobar que Uvicorn escucha en `0.0.0.0:8080`.
- Arranque sin `PORT`: comprobar el puerto documentado `8000`.
- Arranque y `/health` cuando M5/`api.py` esté integrado.
- Inspeccionar imagen y contexto: comprobar que `.env`, claves y cadenas de conexión no aparecen en el historial de capas ni en archivos.
- Configuración de Render: definir las variables en el panel y desplegar con la imagen Docker.

## Riesgos
- **`api.py` aún no existe**: el Dockerfile puede construirse, pero el arranque fallará hasta integrar M5; se mantiene explícito en el plan y no se implementa negocio HTTP dentro de Docker.
- **Índice Chroma ausente**: una instalación limpia no contiene `chroma/` porque está excluido de Git y no se copiará ni distribuirá automáticamente en esta fase. La estrategia de distribución del índice preconstruido queda pendiente antes del despliegue en producción.
- **Dependencias pesadas**: `requirements.txt` incluye modelos y paquetes binarios; el build puede crecer y tardar. Se usa variante slim y caché de pip por capa.
- **Red en build**: pip y, si se usa, la descarga del índice requieren Internet. Se permite para build; los tests no hacen llamadas.
- **Python 3.10**: alguna dependencia futura puede requerir una versión posterior; el build visible fallará y se resolverá antes de modificar la imagen base.
- **Render y `PORT`**: si el comando no interpreta correctamente la variable, Render no podrá alcanzar el servicio. Se prueba con un puerto distinto de `8000`.
- **Escalado horizontal**: `--workers 1` no impide que Render cree varias réplicas. El despliegue debe mantener una sola instancia mientras existan checkpoints y planes pendientes en memoria, como exige la constitución §12.
- **Secretos**: `.dockerignore` debe aparecer desde el primer cambio y debe cubrir `.env`, `.env.*`, `venv/`, `.venv/` y cualquier archivo de credenciales. La excepción deliberada puede ser solo `.env.example`.
- **Log de acceso**: `--no-access-log` evita el acceso log de Uvicorn, pero los logs personalizados de la aplicación no pueden registrar claves ni `DATABASE_URL` según la constitución.

## Trazabilidad
| RF | Parte del plan | Test |
|---|---|---|
| RF-1 | Crear `Dockerfile` | `tests/test_docker_config.py::test_dockerfile_usa_python_310` + build manual |
| RF-2 | Capa de instalación en `Dockerfile` | `tests/test_docker_config.py::test_instala_requirements` + build manual |
| RF-3 | CMD Uvicorn con `api:app` | `tests/test_docker_config.py::test_uvicorn_inicia_api_app` + arranque manual |
| RF-4 | `--host 0.0.0.0` | `tests/test_docker_config.py::test_host_es_todos_los_interfaces` + arranque manual |
| RF-5 | Lectura de `PORT` y fallback `8000` | `tests/test_docker_config.py::test_puerto_render_y_fallback` + arranque manual |
| RF-6 | `--workers 1` | `tests/test_docker_config.py::test_un_solo_worker` |
| RF-7 | `--no-access-log` | `tests/test_docker_config.py::test_no_access_log` |
| RF-8 | `.dockerignore` | `tests/test_docker_config.py::test_dockerignore_excluye_archivos_locales` |
| RF-9 | `.dockerignore` excluye `.env` y secretos | `tests/test_docker_config.py::test_dockerignore_excluye_secretos` + inspección manual de capas |
| RF-10 | `README.md`, variables de entorno y `render.yaml` opcional | `tests/test_docker_config.py::test_documenta_variables_de_entorno` + configuración manual Render |
