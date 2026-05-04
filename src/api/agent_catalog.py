"""Catalogue agents / outils exposé au dashboard (paramètres)."""

from __future__ import annotations

from typing import Any

from backend.agentic.config.config import Config
from backend.agentic.prompts.system import get_system_prompt
from backend.agentic.tools.base import Tool
from backend.agentic.tools.registry import create_default_registry
from backend.agentic.tools.subagents import SubagentTool


def _summarize_tool(tool: Tool) -> dict[str, Any]:
    kind_val: str | None = None
    k = getattr(tool, "kind", None)
    if k is not None:
        try:
            kind_val = k.value
        except Exception:
            kind_val = str(k)
    out: dict[str, Any] = {
        "name": tool.name,
        "description": getattr(tool, "description", "") or "",
        "kind": kind_val,
    }
    try:
        oai = tool.to_openai_schema()
        out["parameters"] = oai.get("parameters")
    except Exception:
        pass
    return out


def build_agent_catalog(config: Config) -> dict[str, Any]:
    """Construit la liste des agents (orchestrateur + sous-agents) et le détail des outils."""
    registry = create_default_registry(config)
    tools_list = registry.get_tools()
    by_name: dict[str, Tool] = {t.name: t for t in tools_list}

    all_summaries = [_summarize_tool(t) for t in tools_list]

    main_prompt = get_system_prompt(config, tools=tools_list)

    principal_description = (
        "Orchestrateur du dashboard CLAIR OBSCUR : qualification de tickets SOC, pipeline logs S3/SQL, "
        "visualisation, délégation aux sous-agents (remédiation MITRE, etc.). Prompt système complet ci‑dessous."
    )

    subagents_payload: list[dict[str, Any]] = []
    for t in tools_list:
        if not isinstance(t, SubagentTool):
            continue
        d = t.definition
        allowed = d.allowed_tools
        if allowed:
            tools_resolved = []
            for name in allowed:
                if name in by_name:
                    tools_resolved.append(_summarize_tool(by_name[name]))
                else:
                    tools_resolved.append(
                        {
                            "name": name,
                            "description": "",
                            "kind": None,
                            "missing": True,
                        }
                    )
        else:
            tools_resolved = list(all_summaries)

        subagents_payload.append(
            {
                "id": t.name,
                "kind": "subagent",
                "internal_name": d.name,
                "description": d.description,
                "prompt": d.goal_prompt,
                "tools": tools_resolved,
                "max_turns": d.max_turns,
                "timeout_seconds": d.timeout_seconds,
            }
        )

    subagents_payload.sort(key=lambda x: x["id"])

    return {
        "principal": {
            "id": "principal",
            "kind": "principal",
            "title": "Agent principal (orchestrateur SOC)",
            "description": principal_description,
            "prompt": main_prompt,
            "tools": all_summaries,
        },
        "subagents": subagents_payload,
    }
