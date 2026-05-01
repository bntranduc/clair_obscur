from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, TypedDict
from urllib.parse import unquote

from backend.log.normalization.types import NormalizedEvent


WINDOW_SECONDS = 18_000


class Signal(TypedDict, total=False):
    rule_id: str
    ts: str
    source_ip: str
    username: str
    hostname: str
    iocs: dict[str, Any]
    evidence_ids: list[str]


def _to_dt(ts: str) -> datetime:
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    return datetime.fromisoformat(ts).astimezone(timezone.utc)


def _safe_unquote(s: str) -> str:
    try:
        return unquote(unquote(s))
    except Exception:
        return s


SQLI_REGEXES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"'\s*or\s+'?\d+'?\s*=\s*'?\d+", re.I), "OR 1=1"),
    (re.compile(r"'\s*--(\s|$|&)", re.I), "comment --"),
    (re.compile(r"\bunion\s+(all\s+)?select\b", re.I), "UNION SELECT"),
    (re.compile(r"\b(pg_)?sleep\s*\(", re.I), "sleep()"),
    (re.compile(r"\bwaitfor\s+delay\b", re.I), "WAITFOR DELAY"),
    (re.compile(r"\binformation_schema\b", re.I), "information_schema"),
    (re.compile(r";\s*drop\s+table\b", re.I), "DROP TABLE"),
]


def _sqli_match_reason(uri: str) -> str | None:
    u = (uri or "").strip()
    if not u:
        return None
    decoded = _safe_unquote(u)
    combined = (u + " " + decoded).lower()
    for rx, reason in SQLI_REGEXES:
        if rx.search(combined):
            return reason
    # fallback: very weak indicators, only keep if clearly suspicious
    if "'" in combined or "--" in combined:
        return "quote/comment"
    return None


def detect_signals_window_1h(
    events: Iterable[NormalizedEvent],
    *,
    # credential stuffing / spray
    cs_failures_threshold: int = 100,
    cs_distinct_users_threshold: int = 10,
    # "taux d'échec important vers un même utilisateur"
    cs_user_failures_threshold: int = 50,
    service_user_allowlist: set[str] | None = None,
    # ssh bruteforce
    ssh_failures_threshold: int = 200,
    ssh_burst_n: int = 5,
    ssh_burst_seconds: int = 10,
    # "auth_method exclusivement SSH"
    ssh_exclusive_min_failures: int = 200,
    # "géolocalisation incohérente baseline" (attaquants RU vs legit FR)
    ssh_suspicious_geo: set[str] | None = None,
    ssh_baseline_geo: set[str] | None = None,
    # sqli
    sqli_min_hits: int = 3,
    # "présence d'erreur 500 venant des mêmes IPs" (signal faible)
    sqli_500_threshold: int = 50,
    # "user-agent contient sqlmap"
    sqli_sqlmap_threshold: int = 1,
    max_evidence_ids: int = 20,
) -> list[Signal]:
    """Deterministic detections on a 1-hour window (MVP).

    Returns a list of `Signal` objects, meant to be fed into an aggregator.
    """
    if service_user_allowlist is None:
        service_user_allowlist = {"monitoring", "backup_svc", "prometheus_svc"}
    if ssh_suspicious_geo is None:
        ssh_suspicious_geo = {"RU"}
    if ssh_baseline_geo is None:
        ssh_baseline_geo = {"FR"}

    # --- Credential stuffing candidates (auth failures grouped by source_ip) ---
    auth_by_ip: dict[str, list[NormalizedEvent]] = defaultdict(list)
    auth_user_set_by_ip: dict[str, set[str]] = defaultdict(set)
    auth_failures_by_ip: Counter[str] = Counter()
    # "taux d'échec important vers un même utilisateur"
    auth_failures_by_user: Counter[str] = Counter()
    auth_by_user: dict[str, list[NormalizedEvent]] = defaultdict(list)

    # --- SSH bruteforce (auth_method=ssh failures grouped by source_ip) ---
    ssh_failures_by_ip: dict[str, list[datetime]] = defaultdict(list)
    ssh_methods_by_ip: dict[str, Counter[str]] = defaultdict(Counter)
    ssh_geo_by_ip: dict[str, Counter[str]] = defaultdict(Counter)

    # --- SQLi hits grouped by (source_ip, hostname) ---
    sqli_hits: dict[tuple[str, str], list[tuple[str, str, str]]] = defaultdict(list)  # (ts, uri, reason)
    sqli_500_by_ip: Counter[str] = Counter()
    sqli_sqlmap_by_ip: Counter[str] = Counter()

    # Helper to capture evidence ids
    def _evidence_id(e: NormalizedEvent) -> str | None:
        return (e.get("raw_ref") or {}).get("raw_id")

    for e in events:
        src = e.get("source_ip")
        ts = e.get("timestamp")
        if not src or not ts:
            continue

        # AUTH rules
        if e.get("log_source") == "authentication":
            status = e.get("status")
            user = e.get("username")
            if status == "failure":
                auth_by_ip[src].append(e)
                auth_failures_by_ip[src] += 1
                if user and user not in service_user_allowlist:
                    auth_user_set_by_ip[src].add(user)
                if user and user not in service_user_allowlist:
                    auth_failures_by_user[user] += 1
                    auth_by_user[user].append(e)

            # SSH bruteforce candidates
            method = e.get("auth_method") or ""
            if method:
                ssh_methods_by_ip[src][str(method)] += 1
            geo = e.get("geolocation_country")
            if geo:
                ssh_geo_by_ip[src][str(geo)] += 1
            if method == "ssh" and status == "failure":
                ssh_failures_by_ip[src].append(_to_dt(ts))

        # APP rules (SQLi)
        if e.get("log_source") == "application":
            uri = e.get("uri") or ""
            host = e.get("hostname") or ""
            reason = _sqli_match_reason(uri)
            if reason and host:
                sqli_hits[(src, host)].append((ts, uri, reason))
            # 500 burst indicator (weak, per text)
            if e.get("status_code") == 500:
                sqli_500_by_ip[src] += 1
            # sqlmap UA (strong)
            ua = (e.get("user_agent") or "").lower()
            if "sqlmap" in ua:
                sqli_sqlmap_by_ip[src] += 1

    signals: list[Signal] = []

    # --- Emit CREDENTIAL_STUFFING signals ---
    for ip, fails in auth_failures_by_ip.items():
        distinct_users = len(auth_user_set_by_ip[ip])
        if fails >= cs_failures_threshold and distinct_users >= cs_distinct_users_threshold:
            ev_ids: list[str] = []
            for ev in auth_by_ip[ip]:
                rid = _evidence_id(ev)
                if rid:
                    ev_ids.append(rid)
                if len(ev_ids) >= max_evidence_ids:
                    break
            # timestamp range for the signal: use min/max in this window
            ts_list = [ev.get("timestamp") for ev in auth_by_ip[ip] if ev.get("timestamp")]
            sig_ts = min(ts_list) if ts_list else None
            if sig_ts:
                signals.append(
                    {
                        "rule_id": "CREDENTIAL_STUFFING",
                        "ts": sig_ts,
                        "source_ip": ip,
                        "iocs": {
                            "failures": int(fails),
                            "distinct_usernames": int(distinct_users),
                            "window_seconds": WINDOW_SECONDS,
                        },
                        "evidence_ids": ev_ids,
                    }
                )

    # --- Emit CREDENTIAL_STUFFING_BY_USER signals (many failures to same username) ---
    for user, fails in auth_failures_by_user.items():
        if fails < cs_user_failures_threshold:
            continue
        ev_ids: list[str] = []
        for ev in auth_by_user[user]:
            rid = _evidence_id(ev)
            if rid:
                ev_ids.append(rid)
            if len(ev_ids) >= max_evidence_ids:
                break
        ts_list = [ev.get("timestamp") for ev in auth_by_user[user] if ev.get("timestamp")]
        sig_ts = min(ts_list) if ts_list else None
        if sig_ts:
            signals.append(
                {
                    "rule_id": "CREDENTIAL_STUFFING_USER_TARGETED",
                    "ts": sig_ts,
                    "username": user,
                    "iocs": {"failures": int(fails), "window_seconds": WINDOW_SECONDS},
                    "evidence_ids": ev_ids,
                }
            )

    # --- Emit SSH_BRUTEFORCE signals ---
    for ip, dts in ssh_failures_by_ip.items():
        if len(dts) < ssh_failures_threshold:
            # still emit if bursty (human-impossible cadence)
            dts_sorted = sorted(dts)
            burst = False
            j = 0
            for i in range(len(dts_sorted)):
                while dts_sorted[i] - dts_sorted[j] > timedelta(seconds=ssh_burst_seconds):  # type: ignore[name-defined]
                    j += 1
                if i - j + 1 >= ssh_burst_n:
                    burst = True
                    break
            if not burst:
                continue

        dts_sorted = sorted(dts)
        sig_ts = dts_sorted[0].isoformat().replace("+00:00", "Z")
        signals.append(
            {
                "rule_id": "SSH_BRUTEFORCE",
                "ts": sig_ts,
                "source_ip": ip,
                "iocs": {
                    "ssh_failures": int(len(dts)),
                    "window_seconds": WINDOW_SECONDS,
                    "burst_n": ssh_burst_n,
                    "burst_seconds": ssh_burst_seconds,
                },
            }
        )

    # --- Emit SSH_BRUTEFORCE_EXCLUSIVE_METHOD signals (auth_method exclusively ssh) ---
    for ip, methods in ssh_methods_by_ip.items():
        total = sum(methods.values())
        if total <= 0:
            continue
        ssh_only = methods.get("ssh", 0) == total
        if ssh_only and methods.get("ssh", 0) >= ssh_exclusive_min_failures:
            signals.append(
                {
                    "rule_id": "SSH_BRUTEFORCE_SSH_ONLY",
                    "ts": (auth_by_ip.get(ip) or [{}])[0].get("timestamp") or "1970-01-01T00:00:00Z",
                    "source_ip": ip,
                    "iocs": {"auth_methods": dict(methods), "window_seconds": WINDOW_SECONDS},
                }
            )

    # --- Emit SSH_BRUTEFORCE_GEO signals (RU vs baseline FR) ---
    for ip, geos in ssh_geo_by_ip.items():
        if geos.get("RU", 0) > 0 and geos.get("FR", 0) == 0 and sum(geos.values()) >= 10:
            signals.append(
                {
                    "rule_id": "SSH_BRUTEFORCE_SUSPICIOUS_GEO",
                    "ts": (auth_by_ip.get(ip) or [{}])[0].get("timestamp") or "1970-01-01T00:00:00Z",
                    "source_ip": ip,
                    "iocs": {"geo_counts": dict(geos), "baseline": list(ssh_baseline_geo), "window_seconds": WINDOW_SECONDS},
                }
            )

    # --- Emit SQL_INJECTION signals ---
    for (ip, host), hits in sqli_hits.items():
        if len(hits) < sqli_min_hits:
            continue
        # pick earliest ts as representative
        hits_sorted = sorted(hits, key=lambda x: x[0])
        sig_ts, _, _ = hits_sorted[0]
        top_reasons = Counter([r for _, _, r in hits_sorted]).most_common(5)
        top_uris = [u for _, u, _ in hits_sorted[:5]]
        signals.append(
            {
                "rule_id": "SQL_INJECTION",
                "ts": sig_ts,
                "source_ip": ip,
                "hostname": host,
                "iocs": {
                    "hits": int(len(hits_sorted)),
                    "top_reasons": top_reasons,
                    "sample_uris": top_uris,
                    "window_seconds": WINDOW_SECONDS,
                },
            }
        )

    # --- Emit SQL_INJECTION_500_VOLUME signals (weak indicator) ---
    for ip, n500 in sqli_500_by_ip.items():
        if n500 >= sqli_500_threshold:
            signals.append(
                {
                    "rule_id": "SQL_INJECTION_MANY_500",
                    "ts": "1970-01-01T00:00:00Z",
                    "source_ip": ip,
                    "iocs": {"status_code_500": int(n500), "window_seconds": WINDOW_SECONDS},
                }
            )

    # --- Emit SQL_INJECTION_SQLMAP_UA signals (strong indicator) ---
    for ip, n in sqli_sqlmap_by_ip.items():
        if n >= sqli_sqlmap_threshold:
            signals.append(
                {
                    "rule_id": "SQL_INJECTION_SQLMAP_UA",
                    "ts": "1970-01-01T00:00:00Z",
                    "source_ip": ip,
                    "iocs": {"sqlmap_hits": int(n), "window_seconds": WINDOW_SECONDS},
                }
            )

    return signals
