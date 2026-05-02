"""Chat assistant via Amazon Bedrock (Converse)."""

from __future__ import annotations

from typing import Literal

from botocore.exceptions import ClientError
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from api import config
from backend.aws.bedrock.platform_prompt import CHAT_SYSTEM_PROMPT
from backend.model.bedrock_client import MODEL_ID_DEFAULT, bedrock_converse_chat

router = APIRouter(tags=["chat"])

_DEFAULT_SYSTEM = CHAT_SYSTEM_PROMPT


class ChatMessageIn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=50_000)


class ChatRequest(BaseModel):
    messages: list[ChatMessageIn] = Field(..., min_length=1, max_length=48)


class ChatResponse(BaseModel):
    reply: str


@router.post("", response_model=ChatResponse)
def chat_completion(body: ChatRequest) -> ChatResponse:
    if body.messages[-1].role != "user":
        raise HTTPException(
            status_code=400,
            detail="Le dernier message doit être un message utilisateur.",
        )
    model_id = config.BEDROCK_MODEL_ID or MODEL_ID_DEFAULT
    system = config.BEDROCK_CHAT_SYSTEM_PROMPT or _DEFAULT_SYSTEM
    payload = [{"role": m.role, "content": m.content} for m in body.messages]
    try:
        reply = bedrock_converse_chat(
            payload,
            region=config.REGION,
            max_tokens=config.BEDROCK_CHAT_MAX_TOKENS,
            model_id=model_id,
            profile_name=config.AWS_PROFILE,
            system_prompt=system,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except ClientError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    if not reply:
        raise HTTPException(status_code=502, detail="Réponse modèle vide.")
    return ChatResponse(reply=reply)
