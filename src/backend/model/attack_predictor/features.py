from __future__ import annotations

import math
import re
from typing import Any, Mapping

import numpy as np

LOG_SOURCES = ("application", "authentication", "network", "system")
AUTH_STATUSES = ("failure", "success")

NUMERIC_FIELDS = (
    "status_code",
    "response_size",
    "response_time_ms",
    "source_port",
    "destination_port",
    "bytes_sent",
    "bytes_received",
    "packets",
    "duration_ms",
    "pid",
)


def _safe_float(x: Any) -> float:
    if x is None:
        return -1.0
    try:
        v = float(x)
        if math.isnan(v) or math.isinf(v):
            return -1.0
        return v
    except (TypeError, ValueError):
        return -1.0


def _text_blob(ev: Mapping[str, Any]) -> str:
    parts = [
        ev.get("uri"),
        ev.get("message"),
        ev.get("user_agent"),
        ev.get("failure_reason"),
        ev.get("http_method"),
        ev.get("hostname"),
        ev.get("process"),
    ]
    return " ".join(str(p).lower() for p in parts if p is not None and str(p).strip())


_TRAVERSAL = re.compile(r"\.\./|%2e%2e|\\\\|\.\.\\|/etc/passwd|/etc/shadow|\.env\b")
_SQLI = re.compile(r"\bunion\b.*\bselect\b|\bor\b\s+1\s*=\s*1|sleep\s*\(|benchmark\s*\(", re.I)
_SSRF = re.compile(r"169\.254\.169\.254|metadata\.google|10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|127\.0\.0\.1:\d+")
_AUTH_FAIL = re.compile(r"fail|invalid|denied|locked|brute", re.I)
_SSH = re.compile(r"\bsshd\b|ssh\b", re.I)


def event_to_feature_vector(ev: Mapping[str, Any]) -> np.ndarray:
    """Map a ``NormalizedEvent``-like dict to a fixed-length float vector."""
    feats: list[float] = []

    ls = ev.get("log_source")
    for name in LOG_SOURCES:
        feats.append(1.0 if ls == name else 0.0)

    st = ev.get("status")
    for name in AUTH_STATUSES:
        feats.append(1.0 if st == name else 0.0)
    feats.append(1.0 if st not in AUTH_STATUSES and st is not None else 0.0)

    for field in NUMERIC_FIELDS:
        feats.append(_safe_float(ev.get(field)))

    feats.append(min(_safe_float(ev.get("response_size")), 1e7) / 1e6)
    feats.append(min(_safe_float(ev.get("bytes_sent")) + _safe_float(ev.get("bytes_received")), 1e9) / 1e6)

    user = ev.get("username")
    feats.append(1.0 if isinstance(user, str) and len(user) > 0 else 0.0)

    blob = _text_blob(ev)
    feats.append(min(len(blob), 5000) / 1000.0)
    feats.append(1.0 if _TRAVERSAL.search(blob) else 0.0)
    feats.append(1.0 if _SQLI.search(blob) else 0.0)
    feats.append(1.0 if _SSRF.search(blob) else 0.0)
    feats.append(1.0 if _AUTH_FAIL.search(blob) else 0.0)
    feats.append(1.0 if _SSH.search(blob) else 0.0)

    return np.asarray(feats, dtype=np.float32)


FEATURE_DIM = int(event_to_feature_vector({}).shape[0])


def feature_names() -> list[str]:
    names: list[str] = []
    names.extend(f"log_source::{s}" for s in LOG_SOURCES)
    names.extend(f"auth_status::{s}" for s in AUTH_STATUSES)
    names.append("auth_status::other")
    names.extend(f"num::{f}" for f in NUMERIC_FIELDS)
    names.extend(["derived::response_mb", "derived::bytes_total_mb", "derived::has_username"])
    names.extend(
        [
            "text::len_k",
            "text::traversal",
            "text::sqli",
            "text::ssrf",
            "text::auth_fail",
            "text::ssh",
        ]
    )
    return names
