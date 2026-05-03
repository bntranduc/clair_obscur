"""Pont FastAPI ↔ ``backend.agentic`` : flux SSE d'événements agent."""

from __future__ import annotations

import asyncio
import json
import os
from collections import OrderedDict
from enum import Enum
from pathlib import Path
from typing import Any, AsyncIterable, AsyncIterator

_MAX_TOOL_OUTPUT_CHARS = 48_000
_MAX_SESSIONS = max(1, int(os.getenv("AGENTIC_MAX_SESSIONS", "200")))

_sessions: "OrderedDict[str, Any]" = OrderedDict()
_session_locks: dict[str, asyncio.Lock] = {}


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    # .../src/api/agentic_bridge.py → racine dépôt = parents[2]
    return here.parents[2]


def _truncate_tool_payload(data: dict[str, Any]) -> dict[str, Any]:
    out = data.get("output")
    if isinstance(out, str) and len(out) > _MAX_TOOL_OUTPUT_CHARS:
        data = {**data, "output": out[:_MAX_TOOL_OUTPUT_CHARS] + "\n… [truncated for stream]"}
    return data


def _serialize_event(ev: Any) -> dict[str, Any]:
    t = ev.type
    type_str = t.value if isinstance(t, Enum) else str(t)
    data = dict(ev.data) if isinstance(ev.data, dict) else {}
    if type_str == "tool_call_complete":
        data = _truncate_tool_payload(data)
    return {"type": type_str, "data": data}


def _lock_for_session(conversation_id: str) -> asyncio.Lock:
    if conversation_id not in _session_locks:
        _session_locks[conversation_id] = asyncio.Lock()
    return _session_locks[conversation_id]


async def _dispose_agent(agent: Any) -> None:
    try:
        await agent.__aexit__(None, None, None)
    except Exception:
        pass


async def _get_or_create_session_agent(conversation_id: str) -> Any:
    from backend.agentic.agent.agent import Agent
    from backend.agentic.config.config import ApprovalPolicy
    from backend.agentic.config.loader import load_config

    if conversation_id in _sessions:
        agent = _sessions.pop(conversation_id)
        _sessions[conversation_id] = agent
        return agent

    while len(_sessions) >= _MAX_SESSIONS:
        evicted_id, old = _sessions.popitem(last=False)
        _session_locks.pop(evicted_id, None)
        await _dispose_agent(old)

    cfg = load_config(_repo_root())
    cfg.approval = ApprovalPolicy.AUTO
    agent = Agent(cfg)
    await agent.__aenter__()
    _sessions[conversation_id] = agent
    return agent


async def _run_agent_turn(agent: Any, message: str) -> AsyncIterator[str]:
    try:
        async for ev in agent.run(message):
            payload = _serialize_event(ev)
            yield f"data: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n"
    except ValueError as e:
        err = {"type": "agent_error", "data": {"error": str(e)}}
        yield f"data: {json.dumps(err, ensure_ascii=False, default=str)}\n\n"
    except Exception as e:  # noqa: BLE001
        err = {"type": "agent_error", "data": {"error": str(e)}}
        yield f"data: {json.dumps(err, ensure_ascii=False, default=str)}\n\n"


async def _merged_agent_turn_sse(
    agent: Any,
    message: str,
    *,
    conversation_id: str,
) -> AsyncIterator[str]:
    q: asyncio.Queue[tuple[str, str]] = asyncio.Queue()
    agent.session.approval_manager.configure_web(
        sse_bridge_queue=q,
        conversation_id=conversation_id,
        enabled=True,
        plan_risk_gate=True,
    )

    async def pump() -> None:
        try:
            async for ev in agent.run(message):
                payload = _serialize_event(ev)
                line = f"data: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n"
                await q.put(("agent", line))
        except ValueError as e:
            err = {"type": "agent_error", "data": {"error": str(e)}}
            line = f"data: {json.dumps(err, ensure_ascii=False, default=str)}\n\n"
            await q.put(("agent", line))
        except Exception as e:  # noqa: BLE001
            err = {"type": "agent_error", "data": {"error": str(e)}}
            line = f"data: {json.dumps(err, ensure_ascii=False, default=str)}\n\n"
            await q.put(("agent", line))
        finally:
            await q.put(("done", ""))

    task = asyncio.create_task(pump())
    try:
        while True:
            kind, line = await q.get()
            if kind == "done":
                break
            yield line
    finally:
        agent.session.approval_manager.configure_web(
            sse_bridge_queue=None,
            conversation_id=None,
            enabled=False,
            plan_risk_gate=False,
        )
        try:
            await task
        except Exception:  # noqa: BLE001
            pass


async def _yield_from(iterable: AsyncIterable[str]) -> AsyncIterator[str]:
    async for item in iterable:
        yield item


async def iter_agentic_sse(
    message: str,
    conversation_id: str | None = None,
) -> AsyncIterator[str]:
    """Un tour agent ; lignes SSE ``data: {...}\\n\\n``."""
    from backend.agentic.agent.agent import Agent
    from backend.agentic.config.config import ApprovalPolicy
    from backend.agentic.config.loader import load_config

    cid = (conversation_id or "").strip()

    if not cid:
        cfg = load_config(_repo_root())
        cfg.approval = ApprovalPolicy.AUTO
        async with Agent(cfg) as agent:
            async for line in _yield_from(_run_agent_turn(agent, message)):
                yield line
        return

    lock = _lock_for_session(cid)
    async with lock:
        agent = await _get_or_create_session_agent(cid)
        async for line in _yield_from(_merged_agent_turn_sse(agent, message, conversation_id=cid)):
            yield line
