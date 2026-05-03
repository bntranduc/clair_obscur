"""Heuristic « sous-agent » : score de criticité d’une étape (plan + outil + paramètres).

Extensible (LLM ou règles avancées) ; aujourd’hui règles déterministes pour ne pas
multiplier les appels modèle sur chaque outil.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import IntEnum
from typing import Any

from backend.agentic.tools.base import Tool, ToolConfirmation, ToolKind


class RiskLevel(IntEnum):
    LOW = 0
    MEDIUM = 1
    HIGH = 2
    CRITICAL = 3


@dataclass
class PlanRiskAssessment:
    level: RiskLevel
    rationale: str
    """Courte explication affichable dans l’UI d’approbation."""


_PLAN_ESCALATE = re.compile(
    r"(rm\s+-rf|delete\s+all|format\s+disk|exfiltr|curl\s+.*\|\s*(ba)?sh|wget\s+.*\|\s*(ba)?sh|"
    r"drop\s+table|truncate\s+table|shutdown|reboot|chmod\s+777\s+/|"
    r"effacer|supprimer\s+tout|playbook\s+destruct)",
    re.IGNORECASE,
)


def summarize_params(params: dict[str, Any]) -> str:
    try:
        s = json.dumps(params, ensure_ascii=False, default=str)
    except TypeError:
        s = str(params)
    if len(s) > 600:
        return s[:600] + "…"
    return s


def assess_tool_step(
    *,
    plan_text: str | None,
    tool: Tool | None,
    tool_name: str,
    params: dict[str, Any],
    confirmation: ToolConfirmation | None,
) -> PlanRiskAssessment:
    """Combine contexte de plan récent, type d’outil et confirmation mutating."""
    reasons: list[str] = []

    if plan_text and _PLAN_ESCALATE.search(plan_text):
        reasons.append("Le plan mentionne une action potentiellement sensible.")

    tname = tool_name.lower()

    if tname in {"shell", "run_terminal_cmd", "bash"}:
        reasons.append("Exécution de commande shell.")
        cmd = str((params or {}).get("command") or confirmation.command or "")
        if cmd:
            from backend.agentic.safety.approval import is_dangerous_command

            if is_dangerous_command(cmd):
                return PlanRiskAssessment(
                    level=RiskLevel.CRITICAL,
                    rationale="Commande classée dangereuse par la politique shell. "
                    + " ".join(reasons),
                )
        return PlanRiskAssessment(
            level=RiskLevel.HIGH,
            rationale=" ".join(reasons) if reasons else "Commande shell non triviale.",
        )

    if tool and tool.kind in {
        ToolKind.WRITE,
        ToolKind.NETWORK,
        ToolKind.MEMORY,
        ToolKind.SHELL,
    }:
        k = tool.kind.value
        reasons.append(f"Outil en écriture / effet ({k}).")
        level = (
            RiskLevel.HIGH if tool.kind in {ToolKind.NETWORK, ToolKind.SHELL} else RiskLevel.MEDIUM
        )
        return PlanRiskAssessment(
            level=level,
            rationale=" ".join(reasons),
        )

    if confirmation and confirmation.is_dangerous:
        return PlanRiskAssessment(
            level=RiskLevel.HIGH,
            rationale="L’outil signale une opération dangereuse. "
            + (" ".join(reasons) if reasons else ""),
        )

    if confirmation and confirmation.command:
        from backend.agentic.safety.approval import is_dangerous_command

        if is_dangerous_command(confirmation.command):
            return PlanRiskAssessment(
                level=RiskLevel.CRITICAL,
                rationale="Commande dangereuse détectée.",
            )

    if reasons:
        return PlanRiskAssessment(level=RiskLevel.MEDIUM, rationale=" ".join(reasons))

    return PlanRiskAssessment(
        level=RiskLevel.LOW,
        rationale="Lecture ou changement local limité ; criticité faible.",
    )


def must_prompt_user(
    risk: PlanRiskAssessment,
    *,
    threshold: RiskLevel = RiskLevel.HIGH,
) -> bool:
    return risk.level >= threshold
