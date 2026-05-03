from __future__ import annotations
from enum import Enum
from dataclasses import dataclass, field
from typing import Any

from backend.agentic.client.response import TokenUsage
from backend.agentic.tools.base import ToolResult


class AgentEventType(str, Enum):
    # Agent lifecycle
    AGENT_START = "agent_start"
    AGENT_END = "agent_end"
    AGENT_ERROR = "agent_error"

    # Multi-step agent loop (LLM → outils → LLM…), visible dans l’UI
    AGENT_STEP = "agent_step"

    # Tool calls
    TOOL_CALL_START = "tool_call_start"
    TOOL_CALL_COMPLETE = "tool_call_complete"

    # Text streaming
    TEXT_DELTA = "text_delta"
    TEXT_COMPLETE = "text_complete"

    # Raisonnement / chaîne de pensée (modèles compatibles OpenRouter, etc.)
    REASONING_DELTA = "reasoning_delta"
    REASONING_COMPLETE = "reasoning_complete"
    # Plan / résumé haut niveau (ex. reasoning.summary) — UI type Cursor « Planning »
    PLANNING_DELTA = "planning_delta"
    PLANNING_COMPLETE = "planning_complete"
    # Approbation humaine (flux web), après juge de risque plan + politique outil
    APPROVAL_REQUIRED = "approval_required"


@dataclass
class AgentEvent:
    type: AgentEventType
    data: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def agent_start(cls, message: str) -> AgentEvent:
        return cls(
            type=AgentEventType.AGENT_START,
            data={"message": message},
        )

    @classmethod
    def agent_end(
        cls,
        response: str | None = None,
        usage: TokenUsage | None = None,
    ) -> AgentEvent:
        return cls(
            type=AgentEventType.AGENT_END,
            data={
                "response": response,
                "usage": usage.__dict__ if usage else None,
            },
        )

    @classmethod
    def agent_error(
        cls,
        error: str,
        details: dict[str, Any] | None = None,
    ) -> AgentEvent:
        return cls(
            type=AgentEventType.AGENT_ERROR,
            data={"error": error, "details": details or {}},
        )

    @classmethod
    def text_delta(cls, content: str) -> AgentEvent:
        return cls(
            type=AgentEventType.TEXT_DELTA,
            data={"content": content},
        )

    @classmethod
    def agent_step(cls, *, phase: str, turn: int) -> AgentEvent:
        return cls(
            type=AgentEventType.AGENT_STEP,
            data={"phase": phase, "turn": turn},
        )

    @classmethod
    def reasoning_delta(cls, content: str) -> AgentEvent:
        return cls(
            type=AgentEventType.REASONING_DELTA,
            data={"content": content},
        )

    @classmethod
    def reasoning_complete(cls, content: str) -> AgentEvent:
        return cls(
            type=AgentEventType.REASONING_COMPLETE,
            data={"content": content},
        )

    @classmethod
    def planning_delta(cls, content: str) -> AgentEvent:
        return cls(
            type=AgentEventType.PLANNING_DELTA,
            data={"content": content},
        )

    @classmethod
    def planning_complete(cls, content: str) -> AgentEvent:
        return cls(
            type=AgentEventType.PLANNING_COMPLETE,
            data={"content": content},
        )

    @classmethod
    def text_complete(cls, content: str) -> AgentEvent:
        return cls(
            type=AgentEventType.TEXT_COMPLETE,
            data={"content": content},
        )

    @classmethod
    def tool_call_start(cls, call_id: str, name: str, arguments: dict[str, Any]):
        return cls(
            type=AgentEventType.TOOL_CALL_START,
            data={
                "call_id": call_id,
                "name": name,
                "arguments": arguments,
            },
        )

    @classmethod
    def tool_call_complete(
        cls,
        call_id: str,
        name: str,
        result: ToolResult,
    ):
        return cls(
            type=AgentEventType.TOOL_CALL_COMPLETE,
            data={
                "call_id": call_id,
                "name": name,
                "success": result.success,
                "output": result.output,
                "error": result.error,
                "metadata": result.metadata,
                "diff": result.diff.to_diff() if result.diff else None,
                "truncated": result.truncated,
                "exit_code": result.exit_code,
            },
        )
