from __future__ import annotations

import os
from typing import Optional

import boto3
from botocore.config import Config

MODEL_ID_DEFAULT = "eu.anthropic.claude-opus-4-6-v1"


def _resolve_bedrock_credentials(
    aws_access_key_id: Optional[str],
    aws_secret_access_key: Optional[str],
    aws_session_token: Optional[str],
) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Priorité : arguments explicites, puis variables d'environnement du processus.

    Si ``AWS_ACCESS_KEY_ID`` et ``AWS_SECRET_ACCESS_KEY`` sont définis dans l'environnement
    (ex. conteneur Docker ``-e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY``), boto3 les utilise
    explicitement et **ne tombe pas** sur le rôle instance EC2. Sinon chaîne par défaut boto3
    (profil, rôle instance, etc.).
    """
    if (aws_access_key_id or "").strip() and (aws_secret_access_key or "").strip():
        return (
            aws_access_key_id.strip(),
            aws_secret_access_key.strip(),
            (aws_session_token or "").strip() or None,
        )
    ak = (os.getenv("AWS_ACCESS_KEY_ID") or "").strip()
    sk = (os.getenv("AWS_SECRET_ACCESS_KEY") or "").strip()
    st = (os.getenv("AWS_SESSION_TOKEN") or "").strip() or None
    if ak and sk:
        return ak, sk, st
    return None, None, None


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

    ak, sk, st = _resolve_bedrock_credentials(
        aws_access_key_id, aws_secret_access_key, aws_session_token
    )
    session = boto3.Session(
        region_name=region,
        aws_access_key_id=ak,
        aws_secret_access_key=sk,
        aws_session_token=st,
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
