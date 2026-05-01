from __future__ import annotations

from typing import Any

from .types import NormalizedEvent, RawRef


ALL_FIELDS: tuple[str, ...] = (
    "timestamp",
    "log_source",
    "action",
    "auth_method",
    "bytes_received",
    "bytes_sent",
    "destination_ip",
    "destination_port",
    "duration_ms",
    "facility",
    "failure_reason",
    "geolocation_country",
    "geolocation_lat",
    "geolocation_lon",
    "hostname",
    "http_method",
    "message",
    "packets",
    "pid",
    "process",
    "protocol",
    "referer",
    "response_size",
    "response_time_ms",
    "session_id",
    "severity",
    "source_ip",
    "source_port",
    "status",
    "status_code",
    "uri",
    "user_agent",
    "username",
)


def get_log_kind(raw: dict[str, Any]) -> str:
    """Return the log kind from a raw _source dict (e.g. 'authentication').

    This is a small helper for routing/grouping before normalization.
    """
    return raw.get("log_source")


def normalize(raw: dict[str, Any], raw_ref: RawRef | None = None) -> NormalizedEvent:
    """Return a 'full' normalized dict with all known keys.

    Any missing fields are set to None.
    """
    out: NormalizedEvent = {k: raw.get(k) for k in ALL_FIELDS}
    if raw_ref:
        out["raw_ref"] = raw_ref
    return out

