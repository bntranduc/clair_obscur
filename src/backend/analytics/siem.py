"""
Tableau de bord SIEM : agrégations OpenSearch (volume, temps, sources, réseau, auth).

Champs attendus dans l’index (ex. ``logs-raw``) : ``timestamp``, ``log_source``,
``source_ip``, ``protocol``, ``action`` (flux réseau), ``status`` (auth), ``severity`` (system).
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from backend.analytics.opensearch_client import build_client

DEFAULT_INDEX = os.getenv("OPENSEARCH_INDEX", "logs-raw")
TS_FIELD = os.getenv("OPENSEARCH_TIMESTAMP_FIELD", "timestamp")
GEO_LOG_SAMPLE_SIZE = min(int(os.getenv("SIEM_GEO_SAMPLE_SIZE", "3000")), 10_000)


def _terms_buckets(agg: dict[str, Any] | None, name: str) -> list[dict[str, Any]]:
    if not agg or name not in agg:
        return []
    buckets = agg[name].get("buckets") or []
    return [{"key": str(b.get("key", "")), "count": int(b.get("doc_count", 0))} for b in buckets]


def _histogram_buckets(agg: dict[str, Any] | None, name: str) -> list[dict[str, Any]]:
    if not agg or name not in agg:
        return []
    out: list[dict[str, Any]] = []
    for b in agg[name].get("buckets") or []:
        ts = b.get("key_as_string") or b.get("key")
        if isinstance(ts, (int, float)):
            ts = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).isoformat().replace("+00:00", "Z")
        out.append({"t": str(ts), "count": int(b.get("doc_count", 0))})
    return out


def _time_range_clause(*, hours: int, ts_field: str, since: str | None, until: str | None) -> dict[str, Any]:
    """Clause ``range`` sur ``ts_field`` : fenêtre fixe ``since``/``until`` (ISO) ou glissante ``now-hours``..``now``."""
    s = (since or "").strip()
    u = (until or "").strip()
    if s and u:
        return {"gte": s, "lte": u}
    return {"gte": f"now-{hours}h", "lte": "now"}


def _display_hours(*, hours: int, since: str | None, until: str | None) -> int:
    s = (since or "").strip()
    u = (until or "").strip()
    if not s or not u:
        return max(1, min(hours, 168))
    try:
        a = datetime.fromisoformat(s.replace("Z", "+00:00"))
        b = datetime.fromisoformat(u.replace("Z", "+00:00"))
        return max(1, int((b - a).total_seconds() / 3600) or 1)
    except (TypeError, ValueError, OSError):
        return max(1, min(hours, 168))


def _search_body(*, hours: int, ts_field: str, since: str | None, until: str | None) -> dict[str, Any]:
    rng = _time_range_clause(hours=hours, ts_field=ts_field, since=since, until=until)
    return {
        "size": 0,
        "track_total_hits": True,
        "query": {"range": {ts_field: rng}},
        "aggs": {
            "over_time": {
                "date_histogram": {
                    "field": ts_field,
                    "fixed_interval": "1h",
                    "min_doc_count": 0,
                }
            },
            "log_sources": {"terms": {"field": "log_source", "size": 20}},
            "top_src_ip": {"terms": {"field": "source_ip", "size": 15, "missing": "N/A"}},
            "unique_src": {"cardinality": {"field": "source_ip", "precision_threshold": 40000}},
            "network_actions": {
                "filter": {"term": {"log_source": "network"}},
                "aggs": {
                    "by_action": {"terms": {"field": "action", "size": 15}},
                    "by_protocol": {"terms": {"field": "protocol", "size": 20}},
                },
            },
            "auth_status": {
                "filter": {"term": {"log_source": "authentication"}},
                "aggs": {"by_status": {"terms": {"field": "status", "size": 10}}},
            },
            "system_sev": {
                "filter": {"term": {"log_source": "system"}},
                "aggs": {"by_severity": {"terms": {"field": "severity", "size": 15}}},
            },
        },
    }


def _parse_geo_hits(hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Extrait lat/lon et métadonnées légères pour la carte (logs avec géolocalisation)."""
    out: list[dict[str, Any]] = []
    for h in hits:
        src = h.get("_source") or {}
        try:
            lat = float(src.get("geolocation_lat"))
            lon = float(src.get("geolocation_lon"))
        except (TypeError, ValueError):
            continue
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            continue
        row: dict[str, Any] = {"lat": lat, "lon": lon}
        ts = src.get("timestamp")
        if ts is not None:
            row["timestamp"] = ts
        for k in ("source_ip", "log_source", "geolocation_country"):
            v = src.get(k)
            if v is not None and v != "":
                row[k] = v
        out.append(row)
    return out


def _fetch_geo_logs(
    client: Any,
    *,
    index: str,
    hours: int,
    ts_field: str,
    size: int,
    since: str | None = None,
    until: str | None = None,
) -> list[dict[str, Any]]:
    rng = _time_range_clause(hours=hours, ts_field=ts_field, since=since, until=until)
    body: dict[str, Any] = {
        "size": max(1, min(size, 10_000)),
        "_source": {
            "includes": [
                "geolocation_lat",
                "geolocation_lon",
                "timestamp",
                "source_ip",
                "log_source",
                "geolocation_country",
            ]
        },
        "query": {
            "bool": {
                "must": [
                    {"range": {ts_field: rng}},
                    {"exists": {"field": "geolocation_lat"}},
                    {"exists": {"field": "geolocation_lon"}},
                ]
            }
        },
        "sort": [{ts_field: {"order": "desc"}}],
    }
    try:
        resp = client.search(index=index, body=body)
        raw_hits = resp.get("hits", {}).get("hits") or []
        return _parse_geo_hits(raw_hits)
    except Exception:
        return []


def _parse_response(body: dict[str, Any], *, hours: int, since: str | None, until: str | None) -> dict[str, Any]:
    total = int(body.get("hits", {}).get("total", {}).get("value", 0) or 0)
    aggs = body.get("aggregations") or {}

    timeline = _histogram_buckets(aggs, "over_time")
    log_sources = _terms_buckets(aggs, "log_sources")
    top_raw = _terms_buckets(aggs, "top_src_ip")
    top_source_ips = [{"ip": x["key"], "count": x["count"]} for x in top_raw if x["key"] != "N/A"]

    uniq = aggs.get("unique_src") or {}
    unique_source_ips = int(uniq.get("value", 0) or 0)

    na = aggs.get("network_actions") or {}
    network_actions = _terms_buckets(na, "by_action")
    protocols = _terms_buckets(na, "by_protocol")

    au = aggs.get("auth_status") or {}
    auth_by_status = _terms_buckets(au, "by_status")

    sy = aggs.get("system_sev") or {}
    system_by_severity = _terms_buckets(sy, "by_severity")

    s = (since or "").strip()
    u = (until or "").strip()
    if s and u:
        try:
            a = datetime.fromisoformat(s.replace("Z", "+00:00"))
            b = datetime.fromisoformat(u.replace("Z", "+00:00"))
            minutes = max((b - a).total_seconds() / 60.0, 1.0)
        except (TypeError, ValueError, OSError):
            minutes = max(hours * 60, 1)
    else:
        minutes = max(hours * 60, 1)
    eps_avg = total / minutes

    h_disp = _display_hours(hours=hours, since=since, until=until)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "time_range_hours": h_disp,
        "total_events": total,
        "events_per_minute_avg": round(eps_avg, 4),
        "unique_source_ips": unique_source_ips,
        "timeline": timeline,
        "log_sources": log_sources,
        "protocols": protocols,
        "network_actions": network_actions,
        "auth_by_status": auth_by_status,
        "top_source_ips": top_source_ips[:15],
        "system_by_severity": system_by_severity,
        "geo_logs": [],
        "data_source": "opensearch",
        "time_filter_since": s or None,
        "time_filter_until": u or None,
    }


def _fallback_dashboard(*, hours: int, since: str | None = None, until: str | None = None) -> dict[str, Any]:
    """Données de démo si OpenSearch indisponible ou agrégation refusée."""
    s_f = (since or "").strip() or None
    u_f = (until or "").strip() or None
    return {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "time_range_hours": hours,
        "total_events": 128_400,
        "events_per_minute_avg": round(128_400 / max(hours * 60, 1), 2),
        "unique_source_ips": 842,
        "timeline": [{"t": f"2026-01-11T{h:02d}:00:00.000Z", "count": 3200 + (h * 127) % 900} for h in range(24)],
        "log_sources": [
            {"key": "network", "count": 52_000},
            {"key": "application", "count": 38_200},
            {"key": "authentication", "count": 24_100},
            {"key": "system", "count": 14_100},
        ],
        "protocols": [
            {"key": "tcp", "count": 28_400},
            {"key": "udp", "count": 14_200},
            {"key": "icmp", "count": 9_400},
        ],
        "network_actions": [
            {"key": "accept", "count": 48_200},
            {"key": "reject", "count": 3_800},
        ],
        "auth_by_status": [
            {"key": "success", "count": 22_400},
            {"key": "failure", "count": 1_700},
        ],
        "top_source_ips": [
            {"ip": "10.0.7.10", "count": 4_200},
            {"ip": "185.220.101.1", "count": 3_100},
            {"ip": "10.0.0.2", "count": 2_800},
            {"ip": "192.168.1.103", "count": 2_400},
            {"ip": "172.16.0.10", "count": 2_100},
        ],
        "system_by_severity": [
            {"key": "info", "count": 11_200},
            {"key": "notice", "count": 2_100},
            {"key": "warning", "count": 800},
        ],
        "geo_logs": [
            {"lat": 52.3676, "lon": 4.9041, "log_source": "authentication", "source_ip": "198.51.100.10"},
            {"lat": 48.8566, "lon": 2.3522, "log_source": "network", "source_ip": "185.220.101.1"},
            {"lat": 50.1109, "lon": 8.6821, "log_source": "authentication", "source_ip": "10.0.0.2"},
            {"lat": 45.7640, "lon": 4.8357, "log_source": "system", "source_ip": "192.168.1.1"},
            {"lat": 40.7128, "lon": -74.0060, "log_source": "application", "source_ip": "203.0.113.5"},
        ],
        "data_source": "demo",
        "time_filter_since": s_f,
        "time_filter_until": u_f,
    }


def get_siem_dashboard(
    *,
    index: str | None = None,
    hours: int = 24,
    ts_field: str | None = None,
    since: str | None = None,
    until: str | None = None,
) -> dict[str, Any]:
    """
    Agrégations SIEM sur la fenêtre ``now-hours .. now`` ou ``since`` / ``until`` (ISO 8601, UTC).

    Retourne toujours un objet JSON valide ; en cas d’erreur réseau / mapping,
    un jeu **demo** est renvoyé (champ ``data_source`` = ``demo``).
    """
    idx = index or DEFAULT_INDEX
    field = ts_field or TS_FIELD
    h = max(1, min(hours, 168))

    try:
        client = build_client()
        body = _search_body(hours=h, ts_field=field, since=since, until=until)
        resp = client.search(index=idx, body=body)
        out = _parse_response(resp, hours=h, since=since, until=until)
        geo = _fetch_geo_logs(
            client,
            index=idx,
            hours=h,
            ts_field=field,
            size=GEO_LOG_SAMPLE_SIZE,
            since=since,
            until=until,
        )
        out["geo_logs"] = geo
        return out
    except Exception:
        out = _fallback_dashboard(
            hours=_display_hours(hours=h, since=since, until=until),
            since=since,
            until=until,
        )
        return out
