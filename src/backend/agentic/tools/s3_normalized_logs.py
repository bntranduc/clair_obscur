"""Outil : charger des événements normalisés depuis S3 (même pipeline que l’API dashboard)."""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

from pydantic import BaseModel, Field

from backend.agentic.tools.base import Tool, ToolInvocation, ToolKind, ToolResult
from backend.aws.s3.logs import fetch_normalized_page


class FetchNormalizedLogsParams(BaseModel):
    skip: int = Field(0, ge=0, description="Offset (pagination). Ordre : plus récents en premier.")
    limit: int = Field(
        50,
        ge=1,
        le=500,
        description="Nombre maximum d’événements à retourner (plafond 500).",
    )
    bucket: str | None = Field(
        default=None,
        description="Bucket S3 (défaut : env RAW_LOGS_BUCKET ou valeur projet).",
    )
    prefix: str | None = Field(
        default=None,
        description="Préfixe clés S3 (défaut : env RAW_LOGS_PREFIX).",
    )


MAX_JSON_CHARS = 1_800_000


def _sync_fetch(p: FetchNormalizedLogsParams) -> tuple[list[dict[str, Any]], bool] | Exception:
    prof = (os.getenv("AWS_PROFILE") or "").strip() or None
    try:
        items, has_more = fetch_normalized_page(
            skip=p.skip,
            limit=p.limit,
            bucket=p.bucket,
            prefix=p.prefix,
            profile_name=prof,
        )
        return (items, has_more)
    except Exception as e:
        return e


class FetchNormalizedLogsFromS3Tool(Tool):
    """Récupère une page de logs déjà normalisés (schéma ``NormalizedEvent``)."""

    name = "fetch_normalized_logs_from_s3"
    description = (
        "Lit les logs bruts depuis S3, les normalise (pipeline CLAIR OBSCUR) et renvoie un tableau JSON "
        "(événements les plus récents en premier). Utiliser avant un filtrage SQL."
    )
    kind = ToolKind.READ
    schema = FetchNormalizedLogsParams

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        p = FetchNormalizedLogsParams(**invocation.params)
        raw = await asyncio.to_thread(_sync_fetch, p)
        if isinstance(raw, Exception):
            return ToolResult.error_result(
                f"Échec lecture S3 / normalisation : {raw}",
                metadata={"error_type": type(raw).__name__},
            )
        items, has_more = raw

        payload: dict[str, Any] = {
            "events": items,
            "count": len(items),
            "has_more": has_more,
            "skip": p.skip,
            "limit": p.limit,
        }
        text = json.dumps(payload, ensure_ascii=False, indent=2)
        truncated = False
        if len(text) > MAX_JSON_CHARS:
            text = text[:MAX_JSON_CHARS] + "\n… [tronqué pour limite taille]"
            truncated = True

        header = (
            f"Événements normalisés : {len(items)} ligne(s), has_more={has_more}. "
            "Le tableau utile pour SQL est la clé JSON « events ».\n\n"
        )
        return ToolResult.success_result(
            header + text,
            truncated=truncated,
            metadata={"row_count": len(items), "has_more": has_more},
        )
