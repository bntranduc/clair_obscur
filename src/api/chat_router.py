"""Route HTTP chat (Bedrock Converse) pour le dashboard Assistant IA."""

from __future__ import annotations

import os
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.aws.bedrock.platform_prompt import CHAT_SYSTEM_PROMPT
from backend.model.bedrock_client import MODEL_ID_DEFAULT, bedrock_converse_chat

router = APIRouter(prefix="/api/v1", tags=["chat"])


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=48_000)


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(..., min_length=1, max_length=48)
    aws_access_key_id: str | None = Field(default=None, description="Optionnel : Bedrock avec ces clés pour cet appel (sinon rôle / env).")
    aws_secret_access_key: str | None = Field(default=None, repr=False)
    aws_session_token: str | None = Field(default=None, repr=False)
    region: str | None = Field(default=None, description="Région Bedrock pour cet appel (sinon AWS_REGION).")


class ChatResponse(BaseModel):
    reply: str


def _messages_for_bedrock(messages: list[ChatMessage]) -> list[dict[str, str]]:
    """Garde une alternance user/assistant exploitable par Converse (premier = user)."""
    out: list[dict[str, str]] = []
    for m in messages[-24:]:
        role = m.role
        text = m.content.strip()
        if not text:
            continue
        if not out:
            if role != "user":
                continue
            out.append({"role": "user", "content": text})
            continue
        prev = out[-1]["role"]
        if role == prev:
            if role == "assistant":
                out[-1]["content"] = f"{out[-1]['content']}\n\n{text}"
            else:
                out[-1]["content"] = f"{out[-1]['content']}\n\n{text}"
            continue
        out.append({"role": role, "content": text})
    if not out or out[-1]["role"] != "user":
        raise ValueError("La conversation doit se terminer par un message utilisateur.")
    return out


@router.post("/chat", response_model=ChatResponse)
def chat_completion(body: ChatRequest) -> ChatResponse:
    """Répond à une conversation (historique + dernier message utilisateur)."""
    try:
        payload = _messages_for_bedrock(body.messages)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    region = (
        (body.region or "").strip()
        or os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "eu-west-3"))
    )
    model_id = (os.getenv("BEDROCK_MODEL_ID") or "").strip() or MODEL_ID_DEFAULT
    max_tokens = int(os.getenv("BEDROCK_CHAT_MAX_TOKENS", os.getenv("BEDROCK_MAX_TOKENS", "4096")))

    ak = (body.aws_access_key_id or "").strip()
    sk = (body.aws_secret_access_key or "").strip()
    inline: dict[str, str] | None = None
    if ak or sk:
        if not ak or not sk:
            raise HTTPException(
                status_code=400,
                detail="aws_access_key_id et aws_secret_access_key sont requis ensemble pour des identifiants dans la requête.",
            )
        inline = {"aws_access_key_id": ak, "aws_secret_access_key": sk}
        st = (body.aws_session_token or "").strip()
        if st:
            inline["aws_session_token"] = st
    prof = None if inline else ((os.getenv("AWS_PROFILE") or "").strip() or None)

    try:
        reply = bedrock_converse_chat(
            payload,
            region=region,
            max_tokens=max_tokens,
            model_id=model_id,
            profile_name=prof,
            inline_credentials=inline,
            system_prompt=CHAT_SYSTEM_PROMPT,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    if not (reply or "").strip():
        raise HTTPException(status_code=502, detail="Réponse vide du modèle.")

    return ChatResponse(reply=reply.strip())
