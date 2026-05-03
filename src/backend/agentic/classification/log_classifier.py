"""
Classifieur de logs firewall (BUG / ATTACK / NORMAL + sévérité).

Porté depuis ESGI cyber_agentic (`log_analyst_agent/log_classifier.py`) avec correction :
les objets JSON contiennent des virgules — on détecte JSON par préfixe `{` avant le parse CSV.
"""

from __future__ import annotations

import csv
import json
import re
from io import StringIO
from typing import Any

# ---------------------------------------------------------------------------
# CONFIGURATION (alignée ESGI / Polars)
# ---------------------------------------------------------------------------

ATTACK_PATTERNS_REASON = [
    r"port scan",
    r"ssh brute force",
    r"brute force",
    r"XSS attempt",
    r"malware",
    r"DDoS",
    r"Potential DDoS",
    r"SQL injection",
    r"Suspicious SQL payload",
    r"Multiple auth failures",
    r"Known malicious domain",
    r"Command injection",
    r"Path traversal",
    r"Buffer overflow",
    r"Ransomware",
]

ATTACK_PATTERNS_FLAGS = [
    r"SCAN",
    r"AUTH_FAIL",
    r"XSS",
    r"MALWARE",
    r"DDOS",
    r"SQLI",
    r"EXPLOIT",
]

HIGH_SEVERITY_ATTACKS = [
    "ssh brute force",
    "brute force",
    "multiple auth failures",
    "malware",
    "known malicious domain",
    "sql injection",
    "suspicious sql payload",
    "ddos",
    "potential ddos",
]

MEDIUM_SEVERITY_ATTACKS = [
    "port scan",
    "xss attempt",
]

SUSPICIOUS_NORMAL_PATTERNS = [
    "suspicious payload",
    "protocol violation",
    "state mismatch",
    "no policy",
]


def _is_null_or_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    return False


def _str(value: Any) -> str:
    return "" if value is None else str(value)


def detect_bug_markers(row: dict[str, Any]) -> list[str]:
    markers: list[str] = []

    timestamp = _str(row.get("timestamp"))
    src_ip = _str(row.get("src_ip"))
    dst_ip = _str(row.get("dst_ip"))
    src_port = _str(row.get("src_port"))
    dst_port = _str(row.get("dst_port"))
    bytes_value = row.get("bytes")
    status = _str(row.get("status")).upper()
    session_id = _str(row.get("session_id"))
    rule_id = row.get("rule_id")

    if timestamp.startswith("CORRUPTED_LINE"):
        markers.append("CORRUPT_LINE")
    if re.search(r"99:99:99", timestamp) or re.search(r"-13-", timestamp) or re.search(r"-99T", timestamp):
        markers.append("MALFORMED_TIMESTAMP")
    if "999.999.999.999" in src_ip:
        markers.append("INVALID_IP_SRC")
    if "999.999.999.999" in dst_ip:
        markers.append("INVALID_IP_DST")

    try:
        if bytes_value is not None and float(bytes_value) < 0:
            markers.append("NEGATIVE_BYTES")
    except (TypeError, ValueError):
        pass

    def _port_is_invalid(port_str: str) -> bool:
        if _is_null_or_empty(port_str):
            return False
        if not port_str.isdigit():
            return True
        try:
            return float(port_str) > 65535
        except ValueError:
            return True

    if _port_is_invalid(src_port):
        markers.append("NONNUMERIC_PORT_SRC")
    if _port_is_invalid(dst_port):
        markers.append("NONNUMERIC_PORT_DST")
    if _is_null_or_empty(src_port):
        markers.append("MISSING_SRC_PORT")
    if _is_null_or_empty(dst_port):
        markers.append("MISSING_DST_PORT")

    if _is_null_or_empty(src_ip):
        markers.append("MISSING_SRC_IP")
    if _is_null_or_empty(dst_ip):
        markers.append("MISSING_DST_IP")
    if _is_null_or_empty(timestamp):
        markers.append("MISSING_TIMESTAMP")
    if _is_null_or_empty(row.get("protocol")):
        markers.append("MISSING_PROTOCOL")
    if _is_null_or_empty(row.get("action")):
        markers.append("MISSING_ACTION")
    if _is_null_or_empty(row.get("reason")):
        markers.append("MISSING_REASON")
    if _is_null_or_empty(row.get("firewall_id")):
        markers.append("MISSING_FIREWALL_ID")

    if session_id and not re.match(r"^[a-zA-Z0-9]{12}$", session_id):
        markers.append("INVALID_SESSION_ID")
    if rule_id is None or rule_id == "":
        markers.append("MISSING_RULE_ID")

    if status in {"ERR", "ERROR", "MALFORMED", "TIMEOUT"}:
        markers.append(f"STATUS_{status}")

    return markers


def is_attack_log(row: dict[str, Any]) -> bool:
    reason = _str(row.get("reason")).lower()
    flags = _str(row.get("flags")).upper()

    for pattern in ATTACK_PATTERNS_REASON:
        if re.search(pattern, reason, re.IGNORECASE):
            return True
    for pattern in ATTACK_PATTERNS_FLAGS:
        if re.search(pattern, flags, re.IGNORECASE):
            return True
    return False


def determine_attack_type(row: dict[str, Any]) -> str | None:
    reason = _str(row.get("reason")).lower()
    if re.search(r"sql injection|suspicious sql payload", reason):
        return "sql_injection"
    if re.search(r"ssh brute force|brute force|multiple auth failures", reason):
        return "brute_force_ssh"
    if re.search(r"malware|known malicious domain", reason):
        return "malware_download"
    if re.search(r"ddos|potential ddos", reason):
        return "ddos"
    if re.search(r"port scan", reason):
        return "port_scan"
    if re.search(r"xss attempt", reason):
        return "xss"
    return None


def classify_log(row: dict[str, Any]) -> str:
    bug_markers = detect_bug_markers(row)
    if bug_markers:
        return "BUG"
    if is_attack_log(row):
        return "ATTACK"
    return "NORMAL"


def get_alert_reason(log: dict[str, Any], category: str, bug_type: str | None = None) -> str:
    if category == "BUG":
        if bug_type:
            return f"Anomalies détectées: {bug_type.replace('|', ', ')}"
        return "Anomalies structurelles/valeurs manquantes détectées."

    if category == "ATTACK":
        reason = _str(log.get("reason"))
        flags = _str(log.get("flags"))
        hints = [part for part in [reason, f"flags={flags}" if flags else ""] if part]
        return " | ".join(hints) if hints else "Signatures d'attaque détectées."

    return "Pas d'indicateurs de menace critiques."


def calculate_severity(log: dict[str, Any], category: str, bug_type: str | None) -> str:
    reason = _str(log.get("reason")).lower()
    flags = _str(log.get("flags")).upper()
    action = _str(log.get("action")).upper()
    bug_type_str = bug_type or ""

    if category == "ATTACK":
        for pattern in HIGH_SEVERITY_ATTACKS:
            if re.search(pattern, reason, re.IGNORECASE):
                return "HIGH"
        if any(token in flags for token in ["AUTH_FAIL", "MALWARE", "SQLI", "DDOS"]):
            return "HIGH"

        for pattern in MEDIUM_SEVERITY_ATTACKS:
            if re.search(pattern, reason, re.IGNORECASE):
                return "MEDIUM"
        if any(token in flags for token in ["SCAN", "XSS"]):
            return "MEDIUM"

        return "MEDIUM" if action in {"DENY", "DROP", "REJECT"} else "LOW"

    if category == "BUG":
        high_markers = {"CORRUPT_LINE", "MALFORMED_TIMESTAMP", "INVALID_IP_SRC", "INVALID_IP_DST"}
        medium_markers = {
            "NEGATIVE_BYTES",
            "NONNUMERIC_PORT_SRC",
            "NONNUMERIC_PORT_DST",
            "MISSING_SRC_PORT",
            "MISSING_DST_PORT",
        }
        bug_tokens = set(bug_type_str.split("|")) if bug_type_str else set()

        if bug_tokens & high_markers:
            return "HIGH"
        if bug_tokens & medium_markers:
            return "MEDIUM"
        if bug_tokens:
            return "LOW"
        return "LOW"

    suspicious = any(re.search(pattern, reason) for pattern in SUSPICIOUS_NORMAL_PATTERNS)
    if suspicious and action in {"DENY", "DROP", "REJECT"}:
        return "MEDIUM"
    if suspicious:
        return "LOW"
    return "LOW"


def build_thought_summary(
    log: dict[str, Any],
    category: str,
    severity: str,
    bug_type: str | None,
    alert_reason: str | None,
) -> str:
    if category == "BUG":
        if bug_type:
            return (
                f"Le log est classé BUG car les anomalies suivantes ont été détectées : {bug_type}. "
                f"Sévérité évaluée à {severity}."
            )
        return f"Des incohérences ont été détectées et justifient un BUG (sévérité {severity})."
    if category == "ATTACK":
        signal = alert_reason or "indicateurs d'attaque"
        return f"Le comportement correspond à une attaque identifiée via {signal}; sévérité estimée à {severity}."
    return "Aucun motif d'attaque ou d'anomalie majeur, trafic considéré comme normal."


def _parse_log_raw_to_dict(log_raw: str) -> dict[str, Any]:
    s = log_raw.strip()
    try:
        if s.startswith("{"):
            parsed = json.loads(s)
            if isinstance(parsed, dict):
                return parsed
            return {"raw": log_raw, "parsed_non_object": parsed}
        if "," in s:
            headers = [
                "timestamp",
                "firewall_id",
                "src_ip",
                "dst_ip",
                "src_port",
                "dst_port",
                "protocol",
                "action",
                "bytes",
                "duration_ms",
                "rule_id",
                "session_id",
                "user",
                "reason",
                "status",
                "flags",
            ]
            reader = csv.reader(StringIO(s))
            values = next(reader)
            values = [v.strip() if v else "" for v in values]

            log_dict: dict[str, Any] = {}
            for i, header in enumerate(headers):
                log_dict[header] = values[i] if i < len(values) else ""

            for key in ["src_port", "dst_port", "bytes", "duration_ms"]:
                if log_dict.get(key):
                    try:
                        log_dict[key] = float(log_dict[key])
                    except (ValueError, TypeError):
                        pass
            return log_dict
        return json.loads(s)
    except Exception:
        return {"raw": log_raw}


def _finalize_classification(log_dict: dict[str, Any]) -> dict[str, Any]:
    category = classify_log(log_dict)
    bug_markers_list = detect_bug_markers(log_dict)
    bug_type = "|".join(bug_markers_list) if bug_markers_list else None
    severity = calculate_severity(log_dict, category, bug_type)
    alert_reason = get_alert_reason(log_dict, category, bug_type)
    thought_summary = build_thought_summary(log_dict, category, severity, bug_type, alert_reason)
    attack_type = determine_attack_type(log_dict) if category == "ATTACK" else None

    return {
        "category": category,
        "bug_type": bug_type,
        "severity": severity,
        "attack_type": attack_type,
        "alert_reason": alert_reason,
        "thought_summary": thought_summary,
        "log": log_dict,
    }


def classify_log_raw(log_raw: str) -> dict[str, Any]:
    """Classifie un log brut : JSON (objet) ou ligne CSV selon le format."""
    log_dict = _parse_log_raw_to_dict(log_raw)
    return _finalize_classification(log_dict)


def classify_log_dict(log_dict: dict[str, Any]) -> dict[str, Any]:
    """Classifie un dictionnaire déjà structuré (ex. ligne firewall exportée)."""
    return _finalize_classification(dict(log_dict))
