from __future__ import annotations

import argparse
import os
from typing import Optional

import boto3
from botocore.config import Config


# Student guide model id (often NOT callable on-demand on some accounts).
GUIDE_MODEL_ID = "anthropic.claude-opus-4-6-v1"
#
# EU inference profile (eu-west-3) — même défaut que l’API modèle (`bedrock_client.MODEL_ID_DEFAULT`).
MODEL_ID_DEFAULT = "eu.anthropic.claude-opus-4-6-v1"


def call_bedrock_claude_opus_4_6(
    prompt: str,
    *,
    region: str = "eu-west-3",
    max_tokens: int = 512,
    model_id: str = MODEL_ID_DEFAULT,
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
    aws_session_token: Optional[str] = None,
) -> str:
    """
    Call Claude on AWS Bedrock (Converse API) and return plain text.

    Credentials: si les trois paramètres optionnels sont None, boto3 utilise sa chaîne par défaut
    (variables d'environnement sans lecture explicite, profil ~/.aws, rôle instance, etc.).
    Pour forcer des clés explicites, les passer telles quelles (comme le fait ``main()``).
    """
    if not prompt or not prompt.strip():
        raise ValueError("prompt must be a non-empty string")

    if model_id is None or (isinstance(model_id, str) and not model_id.strip()):
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
        # Bedrock rejects `temperature` for this model; only send maxTokens.
        inferenceConfig={"maxTokens": int(max_tokens)},
    )

    parts = resp.get("output", {}).get("message", {}).get("content", [])
    texts: list[str] = []
    if isinstance(parts, list):
        for p in parts:
            if isinstance(p, dict) and isinstance(p.get("text"), str):
                texts.append(p["text"])
    return "".join(texts).strip()


def credentials_from_env_strict() -> tuple[str, str, Optional[str]]:
    """
    Lit uniquement les variables d'environnement (pas de chaîne IAM instance / ~/.aws par défaut).

    Obligatoires : AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
    Optionnel : AWS_SESSION_TOKEN (requis pour les clés temporaires STS).
    """
    key_id = (os.environ.get("AWS_ACCESS_KEY_ID") or "").strip()
    secret = (os.environ.get("AWS_SECRET_ACCESS_KEY") or "").strip()
    token_raw = (os.environ.get("AWS_SESSION_TOKEN") or "").strip()
    token: Optional[str] = token_raw if token_raw else None
    if not key_id or not secret:
        raise SystemExit(
            "Ce script n'utilise pas le rôle instance ni la chaîne de credentials par défaut.\n"
            "Exporte AWS_ACCESS_KEY_ID et AWS_SECRET_ACCESS_KEY "
            "(et AWS_SESSION_TOKEN si les clés sont temporaires)."
        )
    return key_id, secret, token


def main() -> int:
    ap = argparse.ArgumentParser(
        description=(
            "Test Bedrock Claude via Converse API. "
            "Utilise uniquement AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY "
            "(et AWS_SESSION_TOKEN optionnel) depuis l'environnement."
        )
    )
    ap.add_argument("--prompt", default="HELLO", help="Prompt text.")
    ap.add_argument("--region", default="eu-west-3", help="AWS region (default: eu-west-3).")
    ap.add_argument(
        "--model-id",
        default=MODEL_ID_DEFAULT,
        help=(
            "Bedrock modelId. If on-demand isn't supported, pass an inference profile ID/ARN. "
            f"Default: {MODEL_ID_DEFAULT}. Guide model id: {GUIDE_MODEL_ID}"
        ),
    )
    ap.add_argument("--max-tokens", type=int, default=256, help="Max tokens for the response.")
    args = ap.parse_args()

    ak, sk, st = credentials_from_env_strict()
    out = call_bedrock_claude_opus_4_6(
        args.prompt,
        region=args.region,
        max_tokens=args.max_tokens,
        model_id=args.model_id,
        aws_access_key_id=ak,
        aws_secret_access_key=sk,
        aws_session_token=st,
    )
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())