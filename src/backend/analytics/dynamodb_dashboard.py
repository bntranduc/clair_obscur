"""Agrégations type SIEM à partir d’une partition DynamoDB (événements ``event``)."""

from __future__ import annotations

import os
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

from boto3.dynamodb.conditions import Key

from backend.aws.dynamodb_normalized_logs import _aws_session, _jsonify_for_api, default_logs_partition_key

# Plafond ``max_items`` : aligné avec ``Query(..., le=…)`` sur ``GET /api/v1/analytics/dynamodb``.
DYNAMODB_ANALYTICS_MAX_ITEMS_CAP = 15_000


def _parse_ts(ts: str | None) -> datetime | None:
    if not ts or not isinstance(ts, str):
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


def _hour_bucket_utc(ts: str | None) -> str:
    d = _parse_ts(ts)
    if d is None:
        return ""
    return d.strftime("%Y-%m-%dT%H:00:00.000Z")


def _minute_bucket_utc(ts: str | None) -> str:
    d = _parse_ts(ts)
    if d is None:
        return ""
    d = d.astimezone(timezone.utc).replace(second=0, microsecond=0)
    return d.strftime("%Y-%m-%dT%H:%M:00.000Z")


def _timeline_bucket_key(ts: str | None, granularity: str) -> str:
    if granularity == "minute":
        return _minute_bucket_utc(ts)
    return _hour_bucket_utc(ts)


def _filter_events_by_log_timestamp(
    events: list[dict[str, Any]],
    since_iso: str | None,
    until_iso: str | None,
) -> list[dict[str, Any]]:
    """Filtre en mémoire sur ``event.timestamp`` (ISO). Inclusif sur ``since`` et ``until``."""
    s_f = (since_iso or "").strip()
    u_f = (until_iso or "").strip()
    if not s_f and not u_f:
        return events
    s_dt = _parse_ts(s_f) if s_f else None
    u_dt = _parse_ts(u_f) if u_f else None
    out: list[dict[str, Any]] = []
    for ev in events:
        ts = ev.get("timestamp")
        d = _parse_ts(ts) if isinstance(ts, str) else None
        if d is None:
            continue
        if s_dt is not None and d < s_dt:
            continue
        if u_dt is not None and d > u_dt:
            continue
        out.append(ev)
    return out


def _query_partition_recent(
    *,
    pk: str,
    max_items: int,
    region: str,
    table: str,
) -> tuple[list[dict[str, Any]], bool]:
    """Lit jusqu’à ``max_items`` événements récents (``pk`` seul, tri ``sk`` décroissant)."""
    session = _aws_session(region)
    tbl = session.resource("dynamodb", region_name=region).Table(table)
    out: list[dict[str, Any]] = []
    lek: dict[str, Any] | None = None
    truncated = False
    key_expr = Key("pk").eq(pk)

    while len(out) < max_items:
        batch = min(1000, max_items - len(out))
        kwargs: dict[str, Any] = {
            "KeyConditionExpression": key_expr,
            "ScanIndexForward": False,
            "Limit": batch,
        }
        if lek:
            kwargs["ExclusiveStartKey"] = lek
        resp = tbl.query(**kwargs)
        for it in resp.get("Items") or []:
            raw_ev = it.get("event") if isinstance(it.get("event"), dict) else {}
            ev = _jsonify_for_api(dict(raw_ev))
            if it.get("id") is not None:
                ev["id"] = it["id"]
            out.append(ev)
        lek = resp.get("LastEvaluatedKey")
        if not lek:
            break
        if len(out) >= max_items:
            truncated = True
            break
    return out, truncated


def get_dynamodb_dashboard(
    *,
    pk: str | None = None,
    max_items: int = 15_000,
    region: str | None = None,
    table_name: str | None = None,
    since: str | None = None,
    until: str | None = None,
    timeline_granularity: str = "hour",
) -> dict[str, Any]:
    """Construit un objet compatible ``SiemDashboard`` (champ ``data_source``: ``dynamodb``).

    Lit jusqu’à ``max_items`` lignes récentes sur la partition, applique ensuite un filtre optionnel
    sur le champ ``timestamp`` de chaque log (``since`` / ``until`` inclusifs).
    """
    reg = (region or os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "eu-west-3").strip()
    table = (table_name or os.getenv("DYNAMODB_TABLE", "normalized-logs")).strip()
    pk_resolved = (pk or "").strip() or default_logs_partition_key()
    cap = max(100, min(int(max_items), DYNAMODB_ANALYTICS_MAX_ITEMS_CAP))
    s_f = (since or "").strip()
    u_f = (until or "").strip()
    gran = (timeline_granularity or "hour").strip().lower()
    if gran not in ("hour", "minute"):
        gran = "hour"

    events, truncated = _query_partition_recent(
        pk=pk_resolved,
        max_items=cap,
        region=reg,
        table=table,
    )
    dynamodb_items_fetched = len(events)
    events = _filter_events_by_log_timestamp(events, s_f or None, u_f or None)

    total = len(events)
    by_source = Counter()
    by_timeline: Counter[str] = Counter()
    by_ip = Counter()
    auth_status = Counter()
    protocols = Counter()
    actions = Counter()
    severities = Counter()
    geo_logs: list[dict[str, Any]] = []
    geo_cap = min(int(os.getenv("DYNAMODB_ANALYTICS_GEO_MAX", "400")), 2000)
    parsed_times: list[datetime] = []

    for ev in events:
        ls = ev.get("log_source")
        ls_s = str(ls) if ls is not None else "unknown"
        by_source[ls_s] += 1
        ts = ev.get("timestamp")
        if isinstance(ts, str):
            bk = _timeline_bucket_key(ts, gran)
            if bk:
                by_timeline[bk] += 1
            d = _parse_ts(ts)
            if d:
                parsed_times.append(d)
        sip = ev.get("source_ip")
        if sip not in (None, ""):
            by_ip[str(sip)] += 1
        if ls == "authentication":
            st = ev.get("status")
            auth_status[str(st) if st is not None else "unknown"] += 1
        if ls == "network":
            p = ev.get("protocol")
            protocols[str(p) if p is not None else "unknown"] += 1
            a = ev.get("action")
            actions[str(a) if a is not None else "unknown"] += 1
        if ls == "system":
            sev = ev.get("severity")
            severities[str(sev) if sev is not None else "unknown"] += 1
        if len(geo_logs) < geo_cap:
            try:
                lat = float(ev.get("geolocation_lat"))  # type: ignore[arg-type]
                lon = float(ev.get("geolocation_lon"))  # type: ignore[arg-type]
            except (TypeError, ValueError):
                lat = lon = None
            if lat is not None and lon is not None and (-90 <= lat <= 90) and (-180 <= lon <= 180):
                row: dict[str, Any] = {"lat": lat, "lon": lon}
                for k in ("timestamp", "source_ip", "log_source", "geolocation_country"):
                    v = ev.get(k)
                    if v is not None and v != "":
                        row[k] = v
                geo_logs.append(row)

    timeline = [{"t": t, "count": c} for t, c in sorted(by_timeline.items(), key=lambda x: x[0])]
    log_sources = [{"key": k, "count": v} for k, v in by_source.most_common(20)]
    top_raw = by_ip.most_common(15)
    top_source_ips = [{"ip": k, "count": v} for k, v in top_raw]

    minutes_span = 1.0
    if len(parsed_times) >= 2:
        mn = min(parsed_times)
        mx = max(parsed_times)
        minutes_span = max((mx - mn).total_seconds() / 60.0, 1.0)
    elif len(parsed_times) == 1:
        minutes_span = 1.0
    eps_avg = total / minutes_span if total else 0.0

    hours_window = 24
    if parsed_times:
        mn = min(parsed_times)
        mx = max(parsed_times)
        hours_window = max(int((mx - mn).total_seconds() / 3600) + 1, 1)
    if s_f and u_f:
        try:
            a = datetime.fromisoformat(s_f.replace("Z", "+00:00"))
            b = datetime.fromisoformat(u_f.replace("Z", "+00:00"))
            hours_window = max(int((b - a).total_seconds() / 3600) or 1, 1)
        except (TypeError, ValueError, OSError):
            pass

    ts_first: str | None = None
    ts_last: str | None = None
    if parsed_times:
        mn = min(parsed_times)
        mx = max(parsed_times)
        ts_first = mn.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        ts_last = mx.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    return {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "time_range_hours": hours_window,
        "total_events": total,
        "events_per_minute_avg": round(eps_avg, 4),
        "unique_source_ips": len(by_ip),
        "timeline": timeline,
        "log_sources": log_sources,
        "protocols": [{"key": k, "count": v} for k, v in protocols.most_common(20)],
        "network_actions": [{"key": k, "count": v} for k, v in actions.most_common(20)],
        "auth_by_status": [{"key": k, "count": v} for k, v in auth_status.most_common(10)],
        "top_source_ips": top_source_ips,
        "system_by_severity": [{"key": k, "count": v} for k, v in severities.most_common(15)],
        "geo_logs": geo_logs,
        "data_source": "dynamodb",
        "dynamodb_pk": pk_resolved,
        "dynamodb_items_fetched": dynamodb_items_fetched,
        "dynamodb_items_scanned": dynamodb_items_fetched,
        "dynamodb_truncated": truncated,
        "dynamodb_sample_timestamp_first": ts_first,
        "dynamodb_sample_timestamp_last": ts_last,
        "dynamodb_timeline_granularity": gran,
        "time_filter_since": s_f or None,
        "time_filter_until": u_f or None,
    }
