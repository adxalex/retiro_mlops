# Tareas — Spec 008

> Una tarea cada vez: `/sdd-implementar Tn`. Tests primero (en rojo y luego en verde). Marca `[x]` al terminar.
> Esta spec prepara el contenedor sin modificar el negocio de la API. El arranque con `api:app` se verifica manualmente cuando M5 haya integrado `api.py`.

- [x] T1. Crear el test estático de Docker. (RF-1 a RF-10)
      Tests primero: crear `tests/test_docker_config.py` con lecturas de `Dockerfile`, `.dockerignore` y documentación. Los casos iniciales cubren base Python, instalación de requisitos, Uvicorn, host, puerto, worker, access log, exclusiones y variables de entorno. Mientras no existan los archivos, deben fallar.
      Hecho cuando: `pytest tests/test_docker_config.py -q` falla por implementación ausente y queda listo para pasar en las tareas siguientes.

- [x] T2. Crear la base de la imagen Python e instalar dependencias. (RF-1, RF-2)
      Depende de: T1.
      Implementar en `Dockerfile`: imagen base `python:3.10-slim`, directorio de trabajo `/app`, copia de `requirements.txt`, instalación con `pip --no-cache-dir` y copia del contexto versionado necesario.
      Hecho cuando: `tests/test_docker_config.py::test_dockerfile_usa_python_310` y `tests/test_docker_config.py::test_instala_requirements` pasan; no se copia `chroma/` ni se incorpora un índice local.

- [x] T3. Configurar el arranque Uvicorn, el puerto y el único proceso. (RF-3 a RF-7)
      Depende de: T2.
      Tests primero: completar las aserciones estáticas para `api:app`, `--host 0.0.0.0`, lectura de `PORT` con fallback `8000`, `--workers 1` y `--no-access-log`.
      Implementar el comando de arranque sin declarar manualmente `PORT` en una configuración de Render. Mantener un único worker Uvicorn por contenedor.
      Hecho cuando: `tests/test_docker_config.py::test_uvicorn_inicia_api_app`, `test_host_es_todos_los_interfaces`, `test_puerto_render_y_fallback`, `test_un_solo_worker` y `test_no_access_log` pasan.

- [ ] T4. Crear el contexto Docker seguro. (RF-8, RF-9)
      Depende de: T1.
      Tests primero: completar las aserciones de `.dockerignore` para excluir `.git`, entornos virtuales, cachés, archivos temporales, tests, documentación, datos locales e secretos. Permitir `.env.example`.
      Implementar `.dockerignore` sin copiar `.env`, `.env.*` salvo `.env.example`, credenciales ni carpetas locales. No copiar automáticamente `chroma/`.
      Hecho cuando: `tests/test_docker_config.py::test_dockerignore_excluye_archivos_locales` y `tests/test_docker_config.py::test_dockerignore_excluye_secretos` pasan.

- [ ] T5. Preparar la configuración de producción mediante variables de entorno. (RF-10)
      Depende de: T3.
      Tests primero: completar `tests/test_docker_config.py` para comprobar que `README.md` documenta `API_KEY`, `DATABASE_URL`, `GEMINI_API_KEY` o `GOOGLE_API_KEY`, `AEMET_API_KEY`, `CORS_ORIGINS`, límites y puerto, sin contener valores reales.
      Implementar solo documentación/configuración declarativa; no añadir secretos ni leer `.env` dentro de la imagen.
      Hecho cuando: `pytest tests/test_docker_config.py::test_documenta_variables_de_entorno -q` pasa y la documentación muestra cómo pasar variables al contenedor.

- [ ] T6. Preparar la documentación de construcción, ejecución y Render. (RF-5, RF-10)
      Depende de: T5.
      Actualizar `README.md` con build Docker, ejecución local con `PORT=8080`, puerto predeterminado `8000`, variables Render y la restricción de una sola réplica mientras exista estado en memoria.
      Si se crea `render.yaml`, debe configurar Docker y variables, pero no fijar manualmente `PORT` ni declarar réplicas múltiples.
      Hecho cuando: la documentación incluye los comandos exactos de build/run, explica el fallback de puerto y el escalado horizontal deshabilitado; `render.yaml`, si existe, no contiene una asignación manual de `PORT`.

- [ ] T7. Verificar la imagen manualmente sin dependencias externas. (RF-1 a RF-10)
      Depende de: T2, T3, T4, T6.
      Ejecutar build, arranque local y inspección de contexto. Las pruebas de API real se posponen hasta que M5 integre `api.py`; no se deben usar claves reales ni llamar a LLM, AEMET o PostgreSQL.
      Hecho cuando:
      - `docker build -t retiro-api .` termina con las dependencias instaladas.
      - `docker run --rm -p 8080:8080 -e PORT=8080 retiro-api` muestra a Uvicorn escuchando en `0.0.0.0:8080`, o queda documentado como bloqueado hasta M5 si `api.py` no existe.
      - Ejecutar sin `PORT` muestra el puerto documentado `8000`.
      - Inspeccionar el contexto y las capas confirma que no contienen `.env`, claves ni la cadena de conexión.

- [ ] T8. Validación final RF por RF (`/sdd-validar`). (Todos)
      Depende de: T7.
      Ejecutar `pytest` completo y actualizar [validacion.md](./validacion.md) según la plantilla.
      Hecho cuando: la tabla RF por RF está completa, los criterios manuales tienen resultado explícito y `validacion.md` tiene un veredicto justificado.
