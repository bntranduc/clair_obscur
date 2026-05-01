# Build depuis la racine du repo :
#   docker build -f src/backend/model/Dockerfile -t clair-model .
# Ou : docker compose -f docker-compose.model.yml up --build
#
# Credentials Bedrock : passer --env-file .env au run / Compose (voir model/README.md).
FROM python:3.11-slim

WORKDIR /app
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1
ENV AWS_DEFAULT_REGION=eu-west-3

COPY src /app/src
RUN pip install --no-cache-dir -r /app/src/backend/model/requirements-api.txt

EXPOSE 8080
CMD ["uvicorn", "backend.model.serve_app:app", "--host", "0.0.0.0", "--port", "8080"]
