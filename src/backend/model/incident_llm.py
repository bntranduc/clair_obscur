from __future__ import annotations

import json
import re
from typing import Any, Iterable, Mapping, Sequence

from backend.model.bedrock_client import MODEL_ID_DEFAULT, bedrock_converse_text

DEFAULT_ALLOWED_ATTACK_TYPES: tuple[str, ...] = (
    "ssh_brute_force",
    "credential_stuffing",
    "sql_injection",
    "directory_traversal",
    "ssrf",
    "exfiltration",
)

DEFAULT_DETECTION_TIME_SECONDS = 300


def _extract_json_value(text: str) -> Any:
    t = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", t, re.IGNORECASE)
    if fence:
        t = fence.group(1).strip()
    # Try to locate either a JSON object or a JSON array.
    obj_start = t.find("{")
    obj_end = t.rfind("}")
    arr_start = t.find("[")
    arr_end = t.rfind("]")

    # Prefer array if it appears before an object (we now request a list).
    if arr_start != -1 and arr_end != -1 and (obj_start == -1 or arr_start < obj_start):
        if arr_end <= arr_start:
            raise ValueError("Model response did not contain a valid JSON array")
        return json.loads(t[arr_start : arr_end + 1])

    if obj_start == -1 or obj_end == -1 or obj_end <= obj_start:
        raise ValueError("Model response did not contain a JSON value")
    return json.loads(t[obj_start : obj_end + 1])


def build_prediction_prompt(
    *,
    aggregated_incidents: Sequence[Mapping[str, Any]],
    allowed_attack_types: Iterable[str],
    detection_time_seconds: int = DEFAULT_DETECTION_TIME_SECONDS,
) -> str:
    types_list = "\n".join(f"- {x}" for x in allowed_attack_types)
    incidents_blob = json.dumps(
        list(aggregated_incidents),
        ensure_ascii=False,
        indent=2,
    )
    return f"""You are a SOC analyst assistant. Below are aggregated detection incidents produced by deterministic rules (each item may include rule_id, source_ip, username, time range, indicators).

IMPORTANT: If the aggregated incidents list is empty OR if you conclude there is no attack, DO NOT invent anything. In that case, return an EMPTY response (no JSON, no text).

You must return a LIST of detections (JSON array). Include one detection per distinct attack type you believe is present (you may return 1..N items).

Each detection.detection.attack_type MUST be exactly one value from this closed list (copy the string verbatim):
{types_list}

If signals conflict, include multiple detections if justified (e.g., SSH brute force AND credential stuffing).

Return ONLY valid JSON (no markdown, no commentary) with exactly this shape:
[
  {{
    "challenge_id": "<string; use the same value as detection.attack_type unless the dataset defines another id>",
    "detection": {{
      "attack_type": "<one of the allowed values>",
      "attacker_ips": ["<ipv4 strings, deduplicated, empty if unknown>"],
      "victim_accounts": ["<account names involved as victims or targets, deduplicated>"],
      "attack_start_time": "<ISO 8601 UTC ending with Z>",
      "attack_end_time": "<ISO 8601 UTC ending with Z>",
      "indicators": {{ }}
    }},
    "detection_time_seconds": {detection_time_seconds}
  }}
]

Rules:
- attacker_ips: derive from incident source_ip fields when present; omit empty strings.
- victim_accounts: usernames that appear targeted (e.g. stuffing per-user); omit generic noise if unsure.
- Timestamps: merge overlapping incidents; if unclear use the widest reasonable span from the incidents or empty-window fallback "1970-01-01T00:00:00Z".
- indicators: compact dict summarizing key signals (rule_ids, counts, distinct_usernames, etc.).

Aggregated incidents JSON:
{incidents_blob}
"""


def predict_submission_from_incidents(
    aggregated_incidents: Sequence[Mapping[str, Any]],
    *,
    allowed_attack_types: Sequence[str] | None = None,
    detection_time_seconds: int = DEFAULT_DETECTION_TIME_SECONDS,
    region: str = "eu-west-3",
    model_id: str = MODEL_ID_DEFAULT,
    max_tokens: int = 4096,
    profile_name: str | None = None,
) -> Any:
    allowed = tuple(allowed_attack_types or DEFAULT_ALLOWED_ATTACK_TYPES)
    prompt = build_prediction_prompt(
        aggregated_incidents=aggregated_incidents,
        allowed_attack_types=allowed,
        detection_time_seconds=detection_time_seconds,
    )
    raw = bedrock_converse_text(
        prompt,
        region=region,
        max_tokens=max_tokens,
        model_id=model_id,
        profile_name=profile_name,
    )
    return _extract_json_value(raw)
