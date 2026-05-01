# API dashboard FastAPI (logs S3, alertes prédictions).
# Build depuis la racine du repo :
#   docker build -f src/backend/dashboard/Dockerfile -t clair-dashboard:latest .
# Run — région + CORS (ex. DASHBOARD_CORS_ORIGINS=https://….amplifyapp.com) :
#   docker run --rm -p 8010:8010 -e AWS_REGION=eu-west-3 clair-dashboard:latest
#
# Clés AWS dans le conteneur (S3) — depuis un shell où tu as déjà exporté les variables :
#   sudo -E docker run --rm -p 8010:8010 \
#     -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY -e AWS_SESSION_TOKEN \
#     -e AWS_REGION=eu-west-3 \
#     clair-dashboard:latest
#
# Proxy vers le conteneur modèle sur le même hôte (bridge Linux) :
#   -e PREDICT_API_URL=http://172.17.0.1:8080

FROM python:3.12-slim-bookworm

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src

COPY src/backend/dashboard/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /tmp/requirements.txt && \
    rm /tmp/requirements.txt

# Paquets nécessaires à l'app : api, dashboard, log (normalisation).
COPY src/backend/__init__.py /app/src/backend/__init__.py
COPY src/backend/api /app/src/backend/api
COPY src/backend/dashboard /app/src/backend/dashboard
COPY src/backend/log /app/src/backend/log

EXPOSE 8010

CMD ["uvicorn", "backend.dashboard.main:app", "--host", "0.0.0.0", "--port", "8010"]
