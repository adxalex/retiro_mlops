from fastapi import FastAPI

app = FastAPI(
    title="Retiro Agent API",
    description="API REST para interactuar con el agente multiagente del Retiro",
    version="1.0.0"
)


@app.get("/health")
def health_check():
    """
    Comprueba que la API está funcionando.
    """
    return {
        "status": "ok",
        "message": "Retiro Agent API funcionando correctamente"
    }