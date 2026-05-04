# API dashboard FastAPI (``api.main``) — logs S3, SIEM OpenSearch, chat, agentic.
#
# Build depuis la racine du dépôt :
#   docker build -f src/api/Dockerfile -t clair-backend-api .
#   bash src/api/docker_backend.sh run-detached
#
FROM python:3.12-slim-bookworm

WORKDIR /app
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1
ENV API_PORT=8020

COPY src/api/requirements.txt /tmp/requirements-api.txt
RUN pip install --no-cache-dir -r /tmp/requirements-api.txt

COPY src /app/src

# Catalogue d’alertes (``GET /api/v1/alerts``) — même chemin que le défaut ``database/alerts.json`` à la racine du dépôt.
COPY database /app/database

EXPOSE 8020
CMD ["python", "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8020"]
