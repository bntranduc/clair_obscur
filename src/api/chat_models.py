"""Modèles disponibles pour l'assistant chat (OpenRouter ou Log LLM local)."""

from __future__ import annotations

import json
import os
from typing import Any, AsyncIterator

import httpx

MODEL_OPENROUTER = "openrouter"
MODEL_LOCAL_LOG_LLM = "local-log-llm"

DEFAULT_CHAT_MODEL = MODEL_OPENROUTER

CHAT_MODELS: list[dict[str, str]] = [
    {
        "id": MODEL_OPENROUTER,
        "label": "OpenRouter (Devstral)",
        "description": "Agent SOC complet avec outils (OpenRouter).",
    },
    {
        "id": MODEL_LOCAL_LOG_LLM,
        "label": "Log LLM local (~34M)",
        "description": "Modèle maison entraîné sur logs — explication directe, sans outils.",
    },
]


def normalize_chat_model(model: str | None) -> str:
    mid = (model or "").strip().lower()
    if mid in (MODEL_OPENROUTER, MODEL_LOCAL_LOG_LLM):
        return mid
    return DEFAULT_CHAT_MODEL


def list_chat_models() -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    explain_url = (os.getenv("EXPLAIN_LLM_URL") or "").strip()
    for m in CHAT_MODELS:
        if m["id"] == MODEL_LOCAL_LOG_LLM and not explain_url:
            continue
        out.append(m)
    return out


def explain_llm_base_url() -> str:
    return (os.getenv("EXPLAIN_LLM_URL") or "http://127.0.0.1:8001").rstrip("/")


async def iter_local_log_llm_sse(message: str) -> AsyncIterator[str]:
    """Appelle l'API explain locale et émet des événements SSE agentic."""
    url = f"{explain_llm_base_url()}/explain"
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(url, json={"logs": message})
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as e:
        err = {"type": "agent_error", "data": {"error": f"Log LLM indisponible: {e}"}}
        yield f"data: {json.dumps(err, ensure_ascii=False)}\n\n"
        return

    explanation = str(data.get("explanation") or "").strip()
    if not explanation:
        err = {"type": "agent_error", "data": {"error": "Réponse vide du Log LLM local."}}
        yield f"data: {json.dumps(err, ensure_ascii=False)}\n\n"
        return

    truncated = bool(data.get("truncated"))
    prefix = ""
    if truncated:
        prefix = "_(Entrée tronquée pour tenir dans le contexte du modèle.)_\n\n"

    text = prefix + explanation
    for payload in (
        {"type": "text_delta", "data": {"content": text}},
        {"type": "text_complete", "data": {"content": text}},
    ):
        yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
