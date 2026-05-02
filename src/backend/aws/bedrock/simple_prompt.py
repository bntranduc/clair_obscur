#!/usr/bin/env python3
"""Prompt court vers Bedrock (Converse), avec profil AWS CLI / SSO optionnel."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[3]
if _SRC.name == "src" and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from backend.aws.bedrock.platform_prompt import CHAT_SYSTEM_PROMPT  # noqa: E402
from backend.model.bedrock_client import MODEL_ID_DEFAULT, bedrock_converse_chat  # noqa: E402

_DEFAULT_USER = (
    "En une phrase : à quoi sert Clair Obscur pour une équipe SOC, avec nos logs S3 et Bedrock ?"
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Envoie un texte à Bedrock et affiche la réponse.")
    parser.add_argument(
        "prompt",
        nargs="?",
        default=os.getenv("BEDROCK_PROMPT", _DEFAULT_USER),
        help="Texte utilisateur (sinon variable BEDROCK_PROMPT ou défaut métier Clair Obscur)",
    )
    parser.add_argument("--profile", default=os.getenv("AWS_PROFILE", "").strip() or None, help="Profil AWS CLI")
    parser.add_argument("--region", default=os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "eu-west-3")))
    parser.add_argument("--model", default=os.getenv("BEDROCK_MODEL_ID", MODEL_ID_DEFAULT))
    parser.add_argument("--max-tokens", type=int, default=int(os.getenv("BEDROCK_MAX_TOKENS", "512")))
    args = parser.parse_args()

    try:
        text = bedrock_converse_chat(
            [{"role": "user", "content": args.prompt}],
            region=args.region,
            max_tokens=args.max_tokens,
            model_id=args.model,
            profile_name=args.profile,
            system_prompt=CHAT_SYSTEM_PROMPT,
        )
    except Exception as e:
        print(e, file=sys.stderr)
        return 1
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
