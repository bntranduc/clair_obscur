"""Sous-ensemble d'une alerte brute, pertinent pour le clustering (documentation + filtrage)."""

from __future__ import annotations

from typing import Any, TypedDict


class DetectionCompact(TypedDict, total=False):
    attack_type: str
    attack_start_time: str
    attacker_ips: list[str]
    victim_accounts: list[str]


class AlertClusteringInput(TypedDict, total=False):
    """Champs lus depuis une alerte catalogue pour construire les traits."""

    id: str
    challenge_id: str
    severity: str
    detection: DetectionCompact


def compact_alert_for_clustering(raw: dict[str, Any]) -> dict[str, Any]:
    """
    Extrait uniquement les champs utiles au clustering depuis une alerte API complète.
    Les clés manquantes sont omises ou remplacées par des valeurs sûres.
    """
    det_in = raw.get("detection") if isinstance(raw.get("detection"), dict) else {}
    det: dict[str, Any] = {}
    at = det_in.get("attack_type")
    if isinstance(at, str) and at.strip():
        det["attack_type"] = at.strip()
    ast = det_in.get("attack_start_time")
    if isinstance(ast, str) and ast.strip():
        det["attack_start_time"] = ast.strip()
    ips = det_in.get("attacker_ips")
    if isinstance(ips, list):
        det["attacker_ips"] = [str(x).strip() for x in ips if str(x).strip()]
    vic = det_in.get("victim_accounts")
    if isinstance(vic, list):
        det["victim_accounts"] = [str(x).strip() for x in vic if str(x).strip()]

    out: dict[str, Any] = {
        "id": str(raw.get("id", "") or raw.get("numeric_id", "")),
        "challenge_id": str(raw.get("challenge_id", "") or ""),
        "severity": str(raw.get("severity", "") or ""),
    }
    if det:
        out["detection"] = det
    return out
