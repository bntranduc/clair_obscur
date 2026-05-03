"""Flux SSE agentic et résolution des approbations web."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from api.agentic_bridge import iter_agentic_sse
from backend.agentic.safety.web_approval import resolve as resolve_web_approval

router = APIRouter(prefix="/api/v1/agentic", tags=["agentic"])


class AgenticStreamRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=32_000)
    conversation_id: str | None = Field(
        default=None,
        max_length=128,
        description="Identifiant stable (session UI) pour la mémoire agent.",
    )


@router.post("/stream")
async def stream_agentic(req: AgenticStreamRequest):
    async def event_gen():
        async for chunk in iter_agentic_sse(
            req.message.strip(),
            conversation_id=req.conversation_id,
        ):
            yield chunk

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


class AgenticApprovalRequest(BaseModel):
    conversation_id: str = Field(..., min_length=1, max_length=128)
    approval_id: str = Field(..., min_length=1, max_length=128)
    approved: bool


@router.post("/approval")
async def post_agentic_approval(req: AgenticApprovalRequest):
    ok = resolve_web_approval(
        req.conversation_id.strip(),
        req.approval_id.strip(),
        req.approved,
    )
    return {"ok": ok}
