# Spec 008 — Docker y despliegue de la API

> Estado: Borrador  
> Fecha: 2026-11-26

## Contexto y objetivo

El servicio HTTP desarrollado en la Spec 006 necesita poder ejecutarse en un entorno reproducible y desplegarse en Render.

Se utilizará Docker para empaquetar la aplicación, sus dependencias y los elementos necesarios para su ejecución, evitando depender de la configuración local de cada desarrollador.

## Usuarios / actores

- Desarrolladores: construyen y prueban la imagen Docker.
- Render: ejecuta el contenedor en producción.
- Usuarios: consumen el servicio HTTP desplegado.

## Historias de usuario

- H1: Como desarrollador quiero construir una imagen Docker para ejecutar la API en un entorno reproducible.
- H2: Como responsable del despliegue quiero ejecutar el servicio en Render sin incorporar secretos a la imagen.
- H3: Como operador quiero que el contenedor respete la configuración proporcionada por el entorno de ejecución.

## Requisitos funcionales

- RF-1: EL SISTEMA deberá proporcionar un Dockerfile que permita construir una imagen de la API.
- RF-2: CUANDO se construya la imagen, EL SISTEMA instalará las dependencias declaradas en `requirements.txt`.
- RF-3: CUANDO se ejecute el contenedor, EL SISTEMA iniciará la aplicación mediante Uvicorn utilizando `api:app`.
- RF-4: CUANDO se ejecute el contenedor, EL SISTEMA escuchará en `0.0.0.0`.
- RF-5: CUANDO Render proporcione la variable `PORT`, EL SISTEMA utilizará ese puerto para iniciar el servicio.
- RF-6: EL SISTEMA ejecutará Uvicorn con un único worker.
- RF-7: EL SISTEMA arrancará Uvicorn con `--no-access-log`.
- RF-8: EL SISTEMA excluirá del contexto de construcción los archivos locales, temporales y secretos que no deban formar parte de la imagen.
- RF-9: EL SISTEMA no incorporará credenciales ni archivos `.env` a la imagen Docker.
- RF-10: EL SISTEMA permitirá proporcionar la configuración de producción mediante variables de entorno.

## Requisitos no funcionales

- Seguridad: ningún secreto debe quedar almacenado en las capas de la imagen.
- Reproducibilidad: la construcción debe poder realizarse desde un entorno limpio.
- Mantenibilidad: la configuración Docker debe estar documentada.
- Compatibilidad: utilizar Python 3.10 o superior, respetando la constitución del proyecto.
- Arquitectura: mantener un único proceso de servicio.

## Casos límite

- PORT no definido: deberá utilizarse un puerto predeterminado documentado.
- Dependencias incompatibles: la construcción deberá fallar de forma visible.
- Variable de entorno obligatoria ausente: la aplicación deberá conservar el comportamiento de validación definido en su configuración.
- Archivo `.env` presente localmente: no deberá incorporarse a la imagen.

## Fuera de alcance

- Modificaciones del código de negocio de la API.
- Implementación de endpoints.
- Cambios en PostgreSQL o en los repositorios.
- Desarrollo del frontend Streamlit.
- Kubernetes.
- Varias réplicas o workers.
- Modificaciones de la lógica del agente.

## Criterios de finalización

- La imagen Docker se construye correctamente.
- Las dependencias se instalan correctamente.
- El contenedor utiliza el puerto proporcionado por el entorno.
- Se verifica el arranque de FastAPI cuando M5 esté integrado.
- Se comprueba que los secretos no están incluidos en la imagen.
- Se documentan los pasos de construcción y ejecución.
- La configuración queda preparada para el despliegue en Render.

## Dudas abiertas

- ¿Qué versión concreta de Python utilizaremos como imagen base?
- ¿Qué archivos del proyecto son imprescindibles para ejecutar la API dentro del contenedor?
- ¿Qué configuración específica requiere Render para el despliegue?
- ¿Se necesita un healthcheck Docker adicional al endpoint `/health` de la API?