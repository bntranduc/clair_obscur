#!/usr/bin/env python3
"""Parse une ligne nginx ``combined`` → événement ``application`` normalisé."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

# 203.0.113.1 - - [15/Mar/2026:10:00:00 +0000] "GET /api?id=1' OR '1'='1 HTTP/1.1" 500 123 "-" "sqlmap/1.0"
_COMBINED = re.compile(
    r'^(?P<ip>\S+)\s+\S+\s+\S+\s+\[(?P<ts>[^\]]+)\]\s+'
    r'"(?P<method>[A-Z]+)\s+(?P<uri>\S+)\s+HTTP/[^"]+"\s+'
    r'(?P<status>\d{3})\s+(?P<size>\d+|-)\s+"(?P<referer>[^"]*)"\s+"(?P<ua>[^"]*)"'
)


def _to_iso(ts_raw: str) -> str:
    # 15/Mar/2026:10:00:00 +0000
    try:
        dt = datetime.strptime(ts_raw, "%d/%b/%Y:%H:%M:%S %z")
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_nginx_access_line(line: str, *, hostname: str) -> dict[str, Any] | None:
    m = _COMBINED.match(line.strip())
    if not m:
        return None
    size_raw = m.group("size")
    return {
        "timestamp": _to_iso(m.group("ts")),
        "log_source": "application",
        "source_ip": m.group("ip"),
        "http_method": m.group("method"),
        "uri": m.group("uri"),
        "status_code": int(m.group("status")),
        "response_size": None if size_raw == "-" else int(size_raw),
        "user_agent": m.group("ua"),
        "referer": m.group("referer") or None,
        "hostname": hostname,
    }
