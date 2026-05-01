"""Endpoints racine et santé."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["meta"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/")
def root() -> dict[str, str]:
    return {"service": "clair-obscur-dashboard", "docs": "/docs"}
