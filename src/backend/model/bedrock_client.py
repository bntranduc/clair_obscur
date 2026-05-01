from __future__ import annotations

from typing import Optional

import boto3
from botocore.config import Config

MODEL_ID_DEFAULT = "eu.anthropic.claude-opus-4-6-v1"


def bedrock_converse_text(
    prompt: str,
    *,
    region: str = "eu-west-3",
    max_tokens: int = 512,
    model_id: str = MODEL_ID_DEFAULT,
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
    aws_session_token: Optional[str] = None,
) -> str:
    if not prompt or not prompt.strip():
        raise ValueError("prompt must be a non-empty string")

    if not (model_id or "").strip():
        model_id = MODEL_ID_DEFAULT

    session = boto3.Session(
        region_name=region,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        aws_session_token=aws_session_token,
    )

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
