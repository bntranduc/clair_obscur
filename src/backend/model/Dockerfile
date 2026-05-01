# Build from repo root: docker build -f src/backend/model/Dockerfile -t clair-model .
#
# Credentials Bedrock — deux modes :
#
# 1) Clés dans le conteneur (même principal que ``bedrock_claude.py`` sur l'hôte) :
#    export AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... AWS_SESSION_TOKEN=...
#    docker run --rm -p 8080:8080 \
#      -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY -e AWS_SESSION_TOKEN \
#      -e AWS_REGION=eu-west-3 \
#      -e BEDROCK_MODEL_ID=eu.anthropic.claude-opus-4-6-v1 \
#      clair-model
#    (sans ``-e`` pour les trois premières, les valeurs du shell hôte sont injectées.)
#
# 2) Rôle instance EC2 : ne pas définir ces variables ; boto3 utilisera les métadonnées.
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
