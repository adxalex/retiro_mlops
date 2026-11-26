# Validación — Spec 008

> Fecha: 2026-11-26 · Resultado de `pytest`: 515 passed

| RF | Cómo se comprueba | Test o comprobación manual | Resultado |
|---|---|---|---|
| RF-1 | Manual: revisar y construir el Dockerfile | No existe `Dockerfile` en el repositorio; no hay test específico de Docker. | ❌ |
| RF-2 | Manual: construir la imagen y comprobar `pip install -r requirements.txt` | No existe `Dockerfile`; `requirements.txt` sí está presente, pero no se configura su instalación en una imagen. | ❌ |
| RF-3 | Manual: ejecutar el contenedor y comprobar Uvicorn con `api:app` | No existe `Dockerfile` ni `api.py`; no hay prueba de arranque del contenedor. | ❌ |
| RF-4 | Manual: inspeccionar el comando Uvicorn | No existe Dockerfile ni comando que use `0.0.0.0`. | ❌ |
| RF-5 | Manual: ejecutar con `PORT` definido y comprobar el puerto efectivo | No existe Dockerfile ni configuración de entrada que derive el puerto de `PORT`. | ❌ |
| RF-6 | Manual: inspeccionar el comando Uvicorn | No existe Dockerfile ni configuración de un único worker. | ❌ |
| RF-7 | Manual: inspeccionar el comando Uvicorn | No existe Dockerfile ni opción `--no-access-log`. | ❌ |
| RF-8 | Manual: revisar `.dockerignore` y contexto de Docker | No existe `.dockerignore`; no puede excluirse el contexto de construcción. | ❌ |
| RF-9 | Manual: crear `.env`, construir y revisar capas/contenido | `.env` está excluido por `.gitignore`, pero no existe Dockerfile ni `.dockerignore` y no puede verificarse la imagen. | ❌ |
| RF-10 | Automático parcial: lectura de variables de producción desde el entorno | `tests/test_config_api.py::test_lee_el_entorno`, `tests/test_config_api.py::test_valores_por_defecto`, `tests/test_config_api.py::test_variables_vacias_usan_el_valor_por_defecto` pasan y cubren `API_KEY`, `DATABASE_URL` y límites; no hay Dockerfile que aporte configuración al contenedor. | ⚠️ Parcial |

## Criterios de finalización
- [ ] La imagen Docker se construye correctamente.
- [ ] Las dependencias se instalan correctamente.
- [ ] El contenedor utiliza el puerto proporcionado por el entorno.
- [ ] Se verifica el arranque de FastAPI cuando M5 esté integrado.
- [ ] Se comprueba que los secretos no están incluidos en la imagen.
- [ ] Se documentan los pasos de construcción y ejecución.
- [ ] La configuración queda preparada para el despliegue en Render.

## Comprobaciones adicionales
- Docker no está disponible en el `PATH` del entorno de validación, por lo que tampoco puede ejecutarse una construcción.
- No existen `plan.md` ni `tasks.md` en la carpeta de la spec.
- No existe ningún test cuyo nombre o contenido haga referencia a Docker, `.dockerignore`, Render, `PORT` o `--no-access-log`.

## Fuera de spec
No se ha identificado un comportamiento Docker adicional implementado fuera de la spec.

La configuración de variables de producción existente en `config.py` y sus pruebas pertenecen a la implementación previa del servicio HTTP (Spec 006) y no constituyen una implementación Docker.

## Veredicto
**No — la spec no se cumple.**

La suite completa pasa, pero 515 tests verdes no cubren los requisitos Docker. Faltan el Dockerfile, el `.dockerignore`, el arranque con Uvicorn y la documentación/configuración de Render; por ello no se pueden cumplir ni verificar la mayoría de RF ni los criterios de finalización.
