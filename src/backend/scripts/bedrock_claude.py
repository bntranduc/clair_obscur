from __future__ import annotations

import argparse
from typing import Optional

import boto3
from botocore.config import Config


# Student guide model id (often NOT callable on-demand on some accounts).
GUIDE_MODEL_ID = "anthropic.claude-opus-4-6-v1"
#
# If on-demand throughput isn't supported, Bedrock requires an *inference profile* ID/ARN.
# This repo previously used a profile-like id in eu-west-3. Keep it as the default so the
# script works out of the box for those accounts.
MODEL_ID_DEFAULT = "eu.anthropic.claude-opus-4-7"


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
    Call Claude Opus 4.6 on AWS Bedrock (Converse API) and return plain text.

    Credentials:
    - Prefer using AWS SSO or env vars (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN).
    - You may also pass credentials explicitly to this function.
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


def main() -> int:
    ap = argparse.ArgumentParser(description="Test Bedrock Claude via Converse API.")
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

    out = call_bedrock_claude_opus_4_6(
        args.prompt,
        region=args.region,
        max_tokens=args.max_tokens,
        model_id=args.model_id,
    )
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())