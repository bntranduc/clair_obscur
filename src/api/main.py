"""API minimale : logs S3 + alertes prédictions S3 pour le frontend."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import config
from api.routes import alerts as alerts_routes
from api.routes import chat as chat_routes
from api.routes import logs as logs_routes

app = FastAPI(title="clair-obscur-api", version="0.1.0")
_origins = config.CORS_ORIGINS or ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(logs_routes.router, prefix=f"{config.API_V1_PREFIX}/logs")
app.include_router(alerts_routes.router, prefix=f"{config.API_V1_PREFIX}/alerts")
app.include_router(chat_routes.router, prefix=f"{config.API_V1_PREFIX}/chat")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "clair-obscur-api", "docs": "/docs"}
