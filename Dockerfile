FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY config.py .
COPY src/ src/
COPY data/ data/
COPY scripts/ scripts/

ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "exec python -m uvicorn api:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --no-access-log"]
