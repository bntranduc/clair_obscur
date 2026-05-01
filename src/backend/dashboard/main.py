"""
Application FastAPI dashboard : assemble CORS et les routeurs ``backend.api.endpoints``.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api import config
from backend.api.endpoints import alerts, logs, meta

app = FastAPI(title="clair-obscur-dashboard", version="0.1.0")
_origins = config.CORS_ORIGINS or ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(meta.router)
app.include_router(logs.router, prefix=f"{config.API_V1_PREFIX}/logs")
app.include_router(alerts.router_main, prefix=f"{config.API_V1_PREFIX}/alerts")
app.include_router(alerts.router_tmp, prefix=f"{config.API_V1_PREFIX}/alerts-tmp")
