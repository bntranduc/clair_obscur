# Build from repo root: docker build -f src/backend/model/Dockerfile -t clair-model .
#
# En local (racine du repo) : export PYTHONPATH="$(pwd)/src" puis uvicorn …
#   ou : ./src/backend/scripts/run_model_serve.sh
#
#   docker run --rm -p 8080:8080 -e PYTHONPATH=/app/src \
#     -e AWS_REGION=eu-west-3 -v ~/.aws:/root/.aws:ro clair-model
#
# Ou rôle IAM sur EC2 / variables AWS pour Bedrock.
FROM python:3.11-slim

WORKDIR /app
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1
ENV AWS_DEFAULT_REGION=eu-west-3

COPY src /app/src
RUN pip install --no-cache-dir -r /app/src/backend/model/requirements-api.txt

EXPOSE 8080
CMD ["uvicorn", "backend.model.serve_app:app", "--host", "0.0.0.0", "--port", "8080"]
