from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Iterable, TypedDict


class Incident(TypedDict, total=False):
    rule_id: str
    source_ip: str
    username: str
    hostname: str
    start_time: str
    end_time: str
    indicators: dict[str, Any]
    evidence_ids: list[str]


def _to_dt(ts: str) -> datetime:
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    return datetime.fromisoformat(ts).astimezone(timezone.utc)


def _to_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def aggregate_signals(signals: Iterable[dict[str, Any]], *, max_evidence_ids: int = 50) -> list[Incident]:
    """Merge repeated window-level signals into unique incidents.

    Group key = (rule_id, source_ip, username, hostname).
    Timeline is min/max of valid signal timestamps (ignore 1970 placeholders).
    Indicators are shallow-merged with counters.
    """
    buckets: dict[tuple, dict[str, Any]] = {}
    counters: dict[tuple, Counter[str]] = defaultdict(Counter)

    for s in signals:
        rule = s.get("rule_id")
        ip = s.get("source_ip") or ""
        user = s.get("username") or ""
        host = s.get("hostname") or ""
        key = (rule, ip, user, host)

        ts = s.get("ts") or ""
        dt = None
        if ts and not ts.startswith("1970-01-01"):
            dt = _to_dt(ts)

        b = buckets.get(key)
        if b is None:
            b = buckets[key] = {
                "rule_id": rule,
                "source_ip": ip or None,
                "username": user or None,
                "hostname": host or None,
                "start_dt": dt,
                "end_dt": dt,
                "evidence_ids": [],
                "indicators": {},
            }

        # timeline
        if dt is not None:
            if b["start_dt"] is None or dt < b["start_dt"]:
                b["start_dt"] = dt
            if b["end_dt"] is None or dt > b["end_dt"]:
                b["end_dt"] = dt

        # evidence
        for eid in s.get("evidence_ids") or []:
            if len(b["evidence_ids"]) >= max_evidence_ids:
                break
            if eid and eid not in b["evidence_ids"]:
                b["evidence_ids"].append(eid)

        # indicators (shallow merge)
        iocs = s.get("iocs") or {}
        for k, v in iocs.items():
            # numeric -> keep max
            if isinstance(v, (int, float)):
                prev = b["indicators"].get(k)
                if prev is None or (isinstance(prev, (int, float)) and v > prev):
                    b["indicators"][k] = v
            else:
                # keep counts of stringified values
                counters[key][f"{k}={v}"] += 1

    out: list[Incident] = []
    for key, b in buckets.items():
        indicators = dict(b["indicators"])
        if counters.get(key):
            indicators["top_kv"] = dict(counters[key].most_common(10))

        out.append(
            {
                "rule_id": b["rule_id"],
                "source_ip": b.get("source_ip") or "",
                "username": b.get("username") or "",
                "hostname": b.get("hostname") or "",
                "start_time": _to_z(b["start_dt"]) if b["start_dt"] else "",
                "end_time": _to_z(b["end_dt"]) if b["end_dt"] else "",
                "indicators": indicators,
                "evidence_ids": b["evidence_ids"],
            }
        )

    return out
