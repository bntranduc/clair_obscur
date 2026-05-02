from __future__ import annotations

import os
from typing import Any, Optional

import boto3
from botocore.config import Config

MODEL_ID_DEFAULT = "eu.anthropic.claude-opus-4-6-v1"


def bedrock_converse_text(
    prompt: str,
    *,
    region: str = "eu-west-3",
    max_tokens: int = 512,
    model_id: str = MODEL_ID_DEFAULT,
    profile_name: Optional[str] = None,
) -> str:
    if not prompt or not prompt.strip():
        raise ValueError("prompt must be a non-empty string")

    if not (model_id or "").strip():
        model_id = MODEL_ID_DEFAULT

    prof = profile_name if profile_name is not None else os.getenv("AWS_PROFILE")
    prof = (prof or "").strip() or None
    session_kw: dict[str, Any] = {"region_name": region}
    if prof:
        session_kw["profile_name"] = prof

    session = boto3.Session(**session_kw)

    client = session.client(
        "bedrock-runtime",
        config=Config(retries={"max_attempts": 5, "mode": "standard"}),
    )

    resp = client.converse(
        modelId=model_id,
        messages=[
            {
                "role": "user",
                "content": [{"text": prompt.strip()}],
            }
        ],
        inferenceConfig={"maxTokens": int(max_tokens)},
    )

    parts = resp.get("output", {}).get("message", {}).get("content", [])
    texts: list[str] = []
    if isinstance(parts, list):
        for p in parts:
            if isinstance(p, dict) and isinstance(p.get("text"), str):
                texts.append(p["text"])
    return "".join(texts).strip()


def bedrock_converse_chat(
    messages: list[dict[str, str]],
    *,
    region: str = "eu-west-3",
    max_tokens: int = 4096,
    model_id: str = MODEL_ID_DEFAULT,
    profile_name: Optional[str] = None,
    system_prompt: Optional[str] = None,
) -> str:
    """Conversation multi-tours (rôles ``user`` / ``assistant``) via l’API Converse."""
    if not messages:
        raise ValueError("messages must be non-empty")

    prof = profile_name if profile_name is not None else os.getenv("AWS_PROFILE")
    prof = (prof or "").strip() or None
    session_kw: dict[str, Any] = {"region_name": region}
    if prof:
        session_kw["profile_name"] = prof

    session = boto3.Session(**session_kw)
    client = session.client(
        "bedrock-runtime",
        config=Config(retries={"max_attempts": 5, "mode": "standard"}),
    )

    converse_messages: list[dict[str, Any]] = []
    for m in messages:
        role = (m.get("role") or "").strip()
        text = (m.get("content") or "").strip()
        if role not in ("user", "assistant") or not text:
            continue
        converse_messages.append(
            {"role": role, "content": [{"text": text}]},
        )
    if not converse_messages:
        raise ValueError("no valid user/assistant messages")

    kwargs: dict[str, Any] = {
        "modelId": (model_id or "").strip() or MODEL_ID_DEFAULT,
        "messages": converse_messages,
        "inferenceConfig": {"maxTokens": int(max_tokens)},
    }
    sp = (system_prompt or "").strip()
    if sp:
        kwargs["system"] = [{"text": sp}]

    resp = client.converse(**kwargs)
    parts = resp.get("output", {}).get("message", {}).get("content", [])
    texts_out: list[str] = []
    if isinstance(parts, list):
        for p in parts:
            if isinstance(p, dict) and isinstance(p.get("text"), str):
                texts_out.append(p["text"])
    return "".join(texts_out).strip()
