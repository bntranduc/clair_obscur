from __future__ import annotations

import os
from typing import Any, Optional

from backend.aws.aws_client import AwsClient

MODEL_ID_DEFAULT = "eu.anthropic.claude-opus-4-6-v1"


def _aws_client_for_bedrock(
    *,
    region: str,
    profile_name: Optional[str] = None,
    inline_credentials: Optional[dict[str, str]] = None,
) -> AwsClient:
    if inline_credentials:
        ak = (inline_credentials.get("aws_access_key_id") or "").strip()
        sk = (inline_credentials.get("aws_secret_access_key") or "").strip()
        if not ak or not sk:
            raise ValueError("inline_credentials requires aws_access_key_id and aws_secret_access_key")
        creds: dict[str, str] = {"aws_access_key_id": ak, "aws_secret_access_key": sk}
        st = (inline_credentials.get("aws_session_token") or "").strip()
        if st:
            creds["aws_session_token"] = st
        return AwsClient(region_name=region, credentials=creds)
    prof = profile_name if profile_name is not None else os.getenv("AWS_PROFILE")
    prof = (prof or "").strip() or None
    return AwsClient(region_name=region, profile_name=prof)


def bedrock_converse_text(
    prompt: str,
    *,
    region: str = "eu-west-3",
    max_tokens: int = 512,
    model_id: str = MODEL_ID_DEFAULT,
    profile_name: Optional[str] = None,
    inline_credentials: Optional[dict[str, str]] = None,
) -> str:
    if not prompt or not prompt.strip():
        raise ValueError("prompt must be a non-empty string")

    if not (model_id or "").strip():
        model_id = MODEL_ID_DEFAULT

    client = _aws_client_for_bedrock(
        region=region,
        profile_name=profile_name,
        inline_credentials=inline_credentials,
    ).bedrock_runtime()

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
    inline_credentials: Optional[dict[str, str]] = None,
    system_prompt: Optional[str] = None,
) -> str:
    """Conversation multi-tours (rôles ``user`` / ``assistant``) via l’API Converse."""
    if not messages:
        raise ValueError("messages must be non-empty")

    client = _aws_client_for_bedrock(
        region=region,
        profile_name=profile_name,
        inline_credentials=inline_credentials,
    ).bedrock_runtime()

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
