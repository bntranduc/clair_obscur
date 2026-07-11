# Build depuis la racine du dépôt :
#   docker build -f src/backend/worker/Dockerfile -t clair-predict-worker .
#   docker run --rm --env-file .env clair-predict-worker
FROM python:3.12-slim-bookworm

WORKDIR /app
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

COPY src/backend/worker/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY src /app/src

CMD ["python", "-m", "backend.worker"]
