"""Approbations interactives pour le flux web (SSE + POST résolution)."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

_PendingKey = tuple[str, str]
_pending: dict[_PendingKey, asyncio.Future[bool]] = {}


def create_approval_id() -> str:
    return str(uuid.uuid4())


def register(conversation_id: str, approval_id: str) -> asyncio.Future[bool]:
    loop = asyncio.get_running_loop()
    fut: asyncio.Future[bool] = loop.create_future()
    _pending[(conversation_id.strip(), approval_id)] = fut
    return fut


def resolve(conversation_id: str, approval_id: str, approved: bool) -> bool:
    key: _PendingKey = (conversation_id.strip(), approval_id.strip())
    fut = _pending.pop(key, None)
    if fut is None or fut.done():
        return False
    fut.set_result(approved)
    return True


def pending_snapshot() -> dict[str, Any]:
    return {"count": len(_pending)}
