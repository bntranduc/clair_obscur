"""Outil CLAIR OBSCUR : classification déterministe des logs firewall (ESGI / règles métier)."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field

from backend.agentic.classification.log_classifier import classify_log_dict, classify_log_raw
from backend.agentic.tools.base import Tool, ToolInvocation, ToolKind, ToolResult


class ClassifyFirewallLogParams(BaseModel):
    log_input: str = Field(
        ...,
        min_length=1,
        max_length=100_000,
        description=(
            "Une ligne CSV firewall (16 champs : timestamp, firewall_id, src_ip, dst_ip, "
            "src_port, dst_port, protocol, action, bytes, duration_ms, rule_id, session_id, "
            "user, reason, status, flags) OU un objet JSON sur une ligne (ex. ligne firewall exportée)."
        ),
    )


class ClassifyFirewallLogTool(Tool):
    name = "classify_firewall_log"
    description = (
        "Classifie un événement firewall selon le modèle déterministe CLAIR OBSCUR "
        "(BUG / ATTACK / NORMAL), calcule une sévérité HIGH|MEDIUM|LOW, un type d'attaque "
        "éventuel et un résumé analyste. À utiliser sur une ligne JSON firewall ou une ligne "
        "CSV brute collée par l'analyste."
    )
    kind = ToolKind.READ
    schema = ClassifyFirewallLogParams

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        params = ClassifyFirewallLogParams(**invocation.params)
        raw = params.log_input.strip()
        try:
            if raw.startswith("{"):
                data = json.loads(raw)
                if isinstance(data, dict):
                    result: dict[str, Any] = classify_log_dict(data)
                else:
                    result = classify_log_raw(params.log_input)
            else:
                result = classify_log_raw(params.log_input)
        except json.JSONDecodeError:
            result = classify_log_raw(params.log_input)

        # Réponse compacte pour le LLM : log complet peut être volumineux
        log_preview = result.get("log")
        if isinstance(log_preview, dict) and len(json.dumps(log_preview, ensure_ascii=False)) > 8000:
            result = {
                **{k: v for k, v in result.items() if k != "log"},
                "log": {"_truncated": True, "keys": list(log_preview.keys())},
            }

        text = json.dumps(result, ensure_ascii=False, indent=2)
        return ToolResult.success_result(text, metadata={"category": result.get("category")})
