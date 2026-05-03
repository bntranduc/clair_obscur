"""Classification déterministe des logs firewall (BUG / ATTACK / NORMAL + sévérité).

Porté depuis le projet ESGI cyber_agentic (log_classifier) — règles et scoring alignés.
"""

from backend.agentic.classification.log_classifier import (
    build_thought_summary,
    calculate_severity,
    classify_log,
    classify_log_dict,
    classify_log_raw,
    detect_bug_markers,
    determine_attack_type,
    get_alert_reason,
    is_attack_log,
)

__all__ = [
    "build_thought_summary",
    "calculate_severity",
    "classify_log",
    "classify_log_dict",
    "classify_log_raw",
    "detect_bug_markers",
    "determine_attack_type",
    "get_alert_reason",
    "is_attack_log",
]
