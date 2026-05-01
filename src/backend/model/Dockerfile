# Build from repo root: docker build -f src/backend/model/Dockerfile -t clair-model .
#
# Credentials AWS (obligatoires pour Bedrock) — à passer au run, jamais en ARG/COPY :
#   docker run --rm -p 8080:8080 \
#     -e AWS_ACCESS_KEY_ID=... \
#     -e AWS_SECRET_ACCESS_KEY=... \
#     -e AWS_SESSION_TOKEN=... \
#     -e AWS_REGION=eu-west-3 \
#     -e BEDROCK_MODEL_ID=eu.anthropic.claude-sonnet-4-6 \
#     clair-model
#
# Alternative : monter le profil local (pas de variables pour les clés) :
#   docker run --rm -p 8080:8080 -v ~/.aws:/root/.aws:ro -e AWS_PROFILE=default clair-model
FROM python:3.11-slim

WORKDIR /app
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1
# Défauts non secrets ; surcharger avec -e si besoin.
ENV AWS_DEFAULT_REGION=eu-west-3

COPY src /app/src
RUN pip install --no-cache-dir -r /app/src/backend/model/requirements-api.txt

EXPOSE 8080
CMD ["uvicorn", "backend.model.serve_app:app", "--host", "0.0.0.0", "--port", "8080"]
