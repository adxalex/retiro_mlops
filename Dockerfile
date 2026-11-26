FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY config.py .
COPY src/ src/
COPY data/ data/
COPY scripts/ scripts/
COPY api.py .
COPY security.py .

ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "exec python -m uvicorn api:create_app --factory --host 0.0.0.0 --port ${PORT:-8080} --workers 1 --no-access-log"]