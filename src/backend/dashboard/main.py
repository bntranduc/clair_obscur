"""
Application FastAPI dashboard : assemble CORS et les routeurs ``backend.api.endpoints``.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from backend.api import config
from backend.api.endpoints import alerts, logs, meta, model_predict


class AllowPrivateNetworkMiddleware(BaseHTTPMiddleware):
    """Répond aux préflight Chrome (localhost → EC2) avec ``Access-Control-Allow-Private-Network``."""

    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["Access-Control-Allow-Private-Network"] = "true"
        return response


app = FastAPI(title="clair-obscur-dashboard", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.get_cors_origins(),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(AllowPrivateNetworkMiddleware)

app.include_router(meta.router)
app.include_router(logs.router, prefix=f"{config.API_V1_PREFIX}/logs")
app.include_router(alerts.router_main, prefix=f"{config.API_V1_PREFIX}/alerts")
app.include_router(alerts.router_tmp, prefix=f"{config.API_V1_PREFIX}/alerts-tmp")
app.include_router(model_predict.router, prefix=f"{config.API_V1_PREFIX}/model")
