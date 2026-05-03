# Build depuis la racine du dépôt :
#   docker build -f src/backend/model/Dockerfile -t clair-model-api .
#   docker run --rm -p 8080:8080 -e BEDROCK_MODEL_ID=… clair-model-api
FROM python:3.12-slim-bookworm

WORKDIR /app
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

COPY src/backend/model/requirements-model-api.txt /tmp/requirements-model-api.txt
RUN pip install --no-cache-dir -r /tmp/requirements-model-api.txt

COPY src /app/src

EXPOSE 8080
CMD ["python", "-m", "uvicorn", "backend.model.model_api:app", "--host", "0.0.0.0", "--port", "8080"]
