from __future__ import annotations

import os
from typing import Optional

import anthropic

API_MODEL_ID_DEFAULT = "claude-opus-4-6"


def anthropic_converse_text(
    prompt: str,
    *,
    model_id: str = API_MODEL_ID_DEFAULT,
    max_tokens: int = 4096,
    api_key: Optional[str] = None,
) -> str:
    if not prompt or not prompt.strip():
        raise ValueError("prompt must be a non-empty string")

    key = (api_key or os.getenv("ANTHROPIC_API_KEY") or "").strip()
    if not key:
        raise ValueError("ANTHROPIC_API_KEY is required for direct API backend")

    client = anthropic.Anthropic(api_key=key)

    message = client.messages.create(
        model=(model_id or API_MODEL_ID_DEFAULT).strip(),
        max_tokens=int(max_tokens),
        messages=[{"role": "user", "content": prompt.strip()}],
    )

    texts = [block.text for block in message.content if hasattr(block, "text")]
    return "".join(texts).strip()
