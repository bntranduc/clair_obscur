"""Construction de la matrice de traits numériques à partir d'alertes compactes."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import numpy as np

SEVERITY_RANK: dict[str, float] = {
    "critical": 4.0,
    "high": 3.0,
    "medium": 2.0,
    "low": 1.0,
    "info": 0.5,
}


def _norm_severity(s: str) -> str:
    x = (s or "autre").lower().strip()
    if x in SEVERITY_RANK:
        return x
    return "autre"


def _severity_value(s: str) -> float:
    return SEVERITY_RANK.get(_norm_severity(s), 0.25)


def _parse_iso_ts(iso: str | None) -> float:
    if not iso or not isinstance(iso, str):
        return float("nan")
    try:
        s = iso.strip().replace("Z", "+00:00")
        return datetime.fromisoformat(s).timestamp()
    except (ValueError, TypeError, OSError):
        return float("nan")


def _first_ipv4_octets(ips: Any) -> tuple[float, float, float, float]:
    if not isinstance(ips, list):
        return (0.0, 0.0, 0.0, 0.0)
    for ip in ips:
        if not isinstance(ip, str):
            continue
        parts = ip.strip().split(".")
        if len(parts) == 4:
            try:
                o = [max(0.0, min(255.0, float(int(x)))) / 255.0 for x in parts]
                return (o[0], o[1], o[2], o[3])
            except ValueError:
                continue
    return (0.0, 0.0, 0.0, 0.0)


def _attack_key(a: dict[str, Any]) -> str:
    det = a.get("detection") if isinstance(a.get("detection"), dict) else {}
    at = det.get("attack_type") if isinstance(det, dict) else None
    if isinstance(at, str) and at.strip():
        return at.strip().lower()
    ch = a.get("challenge_id")
    if isinstance(ch, str) and ch.strip():
        return ch.strip().lower()
    return "_unknown"


def build_attack_encoder(alerts: list[dict[str, Any]]) -> dict[str, int]:
    keys = sorted({_attack_key(a) for a in alerts})
    return {k: i for i, k in enumerate(keys)}


def alert_feature_row(a: dict[str, Any], attack_enc: dict[str, int], n_attack: int) -> np.ndarray:
    det = a.get("detection") if isinstance(a.get("detection"), dict) else {}
    sev = _severity_value(str(a.get("severity", "")))
    ts = _parse_iso_ts(det.get("attack_start_time") if isinstance(det, dict) else None)
    ak = _attack_key(a)
    acat = float(attack_enc.get(ak, 0)) / max(1.0, float(max(1, n_attack - 1)))
    o1, o2, o3, o4 = _first_ipv4_octets(det.get("attacker_ips") if isinstance(det, dict) else [])
    vic = det.get("victim_accounts") if isinstance(det, dict) else None
    n_vic = len(vic) if isinstance(vic, list) else 0
    vic_n = min(float(n_vic), 10.0) / 10.0
    row = np.array(
        [sev, ts, acat, o1, o2, o3, o4, vic_n],
        dtype=np.float64,
    )
    return row


def build_feature_matrix(alerts: list[dict[str, Any]]) -> tuple[np.ndarray, list[str], np.ndarray]:
    """
    Retourne ``X`` (n_alerts, 8), ``ids`` alignés, masque ``finite_ts`` pour imputation temps.
    Colonnes : severity, time_unix, attack_cat_norm, ip×4, victim_norm.
    """
    n = len(alerts)
    if n == 0:
        return np.zeros((0, 8), dtype=np.float64), [], np.array([], dtype=bool)

    enc = build_attack_encoder(alerts)
    n_attack = len(enc)

    ids: list[str] = []
    rows: list[np.ndarray] = []
    ts_vals: list[float] = []
    for a in alerts:
        aid = str(a.get("id", "")).strip() or f"idx-{len(ids)}"
        ids.append(aid)
        row = alert_feature_row(a, enc, n_attack)
        rows.append(row)
        ts_vals.append(row[1])

    X = np.vstack(rows)
    finite_ts = np.isfinite(X[:, 1])
    if finite_ts.any():
        t_min = float(np.nanmin(X[:, 1]))
        t_max = float(np.nanmax(X[:, 1]))
        span = t_max - t_min if t_max > t_min else 1.0
        X[:, 1] = np.where(finite_ts, (X[:, 1] - t_min) / span, 0.5)
    else:
        X[:, 1] = 0.5

    return X, ids, finite_ts
