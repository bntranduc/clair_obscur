"""Outil agent : liste des alertes SOC (même source que ``GET /api/v1/alerts``)."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from pydantic import BaseModel

from backend.agentic.tools.base import Tool, ToolInvocation, ToolKind, ToolResult
from backend.alerts.store import load_all_alerts


class GetAllAlertsParams(BaseModel):
    """Paramètres vides : lecture globale du jeu d’alertes."""

    pass


MAX_JSON_CHARS = 1_200_000


def _sync_load() -> dict[str, Any] | Exception:
    try:
        return load_all_alerts()
    except Exception as e:
        return e


class GetAllAlertsTool(Tool):
    """Expose les alertes prédites / enrichies (IDs, sévérités, détection, remédiation)."""

    name = "get_all_alerts"
    description = (
        "Récupère la liste complète des alertes SOC du catalogue CLAIR OBSCUR "
        "(jeu de données JSON : résumés, sévérité, détection, confiance, proposition de remédiation). "
        "À utiliser pour répondre aux questions sur les incidents ouverts ou pour prioriser."
    )
    kind = ToolKind.READ
    schema = GetAllAlertsParams

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        GetAllAlertsParams(**invocation.params)
        raw = await asyncio.to_thread(_sync_load)
        if isinstance(raw, Exception):
            return ToolResult.error_result(
                f"Impossible de charger les alertes : {raw}",
                metadata={"error_type": type(raw).__name__},
            )
        text = json.dumps(raw, ensure_ascii=False, indent=2)
        truncated = False
        if len(text) > MAX_JSON_CHARS:
            text = text[:MAX_JSON_CHARS] + "\n… [tronqué pour limite taille]"
            truncated = True
        header = (
            f"{raw['count']} alerte(s) chargée(s) depuis le catalogue (clé JSON « alerts »).\n\n"
        )
        return ToolResult.success_result(
            header + text,
            truncated=truncated,
            metadata={"alert_count": raw["count"]},
        )
