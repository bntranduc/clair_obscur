"""Agrégations type SIEM à partir d’une partition DynamoDB (événements ``event``)."""

from __future__ import annotations

import os
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

from boto3.dynamodb.conditions import Key

from backend.aws.dynamodb_normalized_logs import _aws_session, _jsonify_for_api, default_logs_partition_key


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


def _sk_exclusive_upper(until_iso: str) -> str | None:
    """Borne supérieure exclusive sur ``sk`` (tri lexicographique = ordre temporel pour nos ISO)."""
    d = _parse_ts(until_iso.strip())
    if d is None:
        return None
    d2 = d + timedelta(milliseconds=1)
    return d2.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _query_all_events(
    *,
    pk: str,
    max_items: int,
    region: str,
    table: str,
    since: str | None = None,
    until: str | None = None,
) -> tuple[list[dict[str, Any]], bool]:
    """Lit jusqu’à ``max_items`` événements (tri ``sk`` décroissant = plus récents d’abord)."""
    session = _aws_session(region)
    tbl = session.resource("dynamodb", region_name=region).Table(table)
    out: list[dict[str, Any]] = []
    lek: dict[str, Any] | None = None
    truncated = False

    s = (since or "").strip()
    u = (until or "").strip()
    key_expr = Key("pk").eq(pk)
    if s:
        key_expr = key_expr & Key("sk").gte(s)
    if u:
        ub = _sk_exclusive_upper(u)
        if ub:
            key_expr = key_expr & Key("sk").lt(ub)

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
    max_items: int = 5000,
    region: str | None = None,
    table_name: str | None = None,
    since: str | None = None,
    until: str | None = None,
) -> dict[str, Any]:
    """Construit un objet compatible ``SiemDashboard`` (champ ``data_source``: ``dynamodb``)."""
    reg = (region or os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "eu-west-3").strip()
    table = (table_name or os.getenv("DYNAMODB_TABLE", "normalized-logs")).strip()
    pk_resolved = (pk or "").strip() or default_logs_partition_key()
    cap = max(100, min(int(max_items), 15_000))
    s_f = (since or "").strip()
    u_f = (until or "").strip()

    events, truncated = _query_all_events(
        pk=pk_resolved,
        max_items=cap,
        region=reg,
        table=table,
        since=s_f or None,
        until=u_f or None,
    )

    total = len(events)
    by_source = Counter()
    by_hour: Counter[str] = Counter()
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
            hb = _hour_bucket_utc(ts)
            if hb:
                by_hour[hb] += 1
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

    timeline = [{"t": t, "count": c} for t, c in sorted(by_hour.items(), key=lambda x: x[0])]
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
        "dynamodb_items_scanned": total,
        "dynamodb_truncated": truncated,
        "time_filter_since": s_f or None,
        "time_filter_until": u_f or None,
    }
