#!/usr/bin/env python3
"""Parse lignes auth (sshd) → événement ``authentication`` normalisé."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

# Mar 15 10:00:00 ip-10-0-1-5 sshd[1234]: Failed password for root from 198.51.100.10 port 22 ssh2
_FAILED = re.compile(
    r"Failed password for (?:invalid user )?(?P<user>\S+) from (?P<ip>\S+) port \d+"
)
_INVALID = re.compile(
    r"Invalid user (?P<user>\S+) from (?P<ip>\S+) port \d+"
)
_ACCEPTED = re.compile(
    r"Accepted password for (?P<user>\S+) from (?P<ip>\S+) port \d+"
)

_SYSLOG_TS = re.compile(r"^(?P<mon>[A-Z][a-z]{2})\s+(?P<day>\d{1,2})\s+(?P<time>\d{2}:\d{2}:\d{2})")


def _syslog_to_iso(line: str, *, year: int | None = None) -> str:
    m = _SYSLOG_TS.match(line)
    if not m:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    yr = year or datetime.now(timezone.utc).year
    raw = f"{yr} {m.group('mon')} {m.group('day')} {m.group('time')}"
    try:
        dt = datetime.strptime(raw, "%Y %b %d %H:%M:%S").replace(tzinfo=timezone.utc)
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_auth_line(line: str, *, hostname: str) -> dict[str, Any] | None:
    text = line.strip()
    if "sshd" not in text and "sudo" not in text:
        return None
    ts = _syslog_to_iso(text)

    m = _FAILED.search(text)
    if m:
        return {
            "timestamp": ts,
            "log_source": "authentication",
            "source_ip": m.group("ip"),
            "username": m.group("user"),
            "status": "failure",
            "auth_method": "ssh",
            "failure_reason": "failed password",
            "hostname": hostname,
        }

    m = _INVALID.search(text)
    if m:
        return {
            "timestamp": ts,
            "log_source": "authentication",
            "source_ip": m.group("ip"),
            "username": m.group("user"),
            "status": "failure",
            "auth_method": "ssh",
            "failure_reason": "invalid user",
            "hostname": hostname,
        }

    m = _ACCEPTED.search(text)
    if m:
        return {
            "timestamp": ts,
            "log_source": "authentication",
            "source_ip": m.group("ip"),
            "username": m.group("user"),
            "status": "success",
            "auth_method": "ssh",
            "hostname": hostname,
        }
    return None
