from __future__ import annotations

import json
import re
from pathlib import Path
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

# Niveaux de criticité classiques (SIEM) — valeur exacte à reproduire dans ``severity``.
SEVERITY_LEVELS_SIEM: tuple[str, ...] = ("low", "medium", "high", "critical")

DEFAULT_DETECTION_TIME_SECONDS = 300

_PROMPT_DIR = Path(__file__).resolve().parent / "prompt"


def _format_embedded_prediction_examples() -> str:
    """Charge les JSON d’exemple sous ``model/prompt/`` pour les injecter dans le prompt."""
    p1 = _PROMPT_DIR / "expected_predictions_example.json"
    p2 = _PROMPT_DIR / "expected_predictions_second_type_example.json"
    ex1 = json.loads(p1.read_text(encoding="utf-8"))
    ex2 = json.loads(p2.read_text(encoding="utf-8"))
    s1 = json.dumps(ex1, ensure_ascii=False, indent=2)
    s2 = json.dumps(ex2, ensure_ascii=False, indent=2)
    return f"""Example 1 — full object shape (fictional values; attack_type ssh_brute_force):
{s1}

Example 2 — same shape, different attack_type (credential_stuffing, fictional):
{s2}"""


def _slice_balanced_json(text: str, start: int, open_ch: str, close_ch: str) -> str | None:
    """Extrait la valeur JSON à partir de ``start`` (``open_ch``) jusqu’à l’accolade/crochet fermant équilibré.

    Gère les ``[`` / ``]`` et ``{`` / ``}`` dans les chaînes JSON (``"``) pour éviter
    l’erreur de ``rfind(']')`` quand le modèle met des crochets dans ``exhaustive_analysis`` / ``reasons``.
    """
    if start < 0 or start >= len(text) or text[start] != open_ch:
        return None
    depth = 0
    i = start
    n = len(text)
    in_str = False
    esc = False
    while i < n:
        c = text[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            i += 1
            continue
        if c == '"':
            in_str = True
            i += 1
            continue
        if c == open_ch:
            depth += 1
        elif c == close_ch:
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
        i += 1
    return None


def _extract_json_value(text: str) -> Any:
    t = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", t, re.IGNORECASE)
    if fence:
        t = fence.group(1).strip()

    arr_start = t.find("[")
    obj_start = t.find("{")

    # Préférer un tableau si le premier ``[`` est avant le premier ``{``.
    if arr_start != -1 and (obj_start == -1 or arr_start < obj_start):
        blob = _slice_balanced_json(t, arr_start, "[", "]")
        if blob:
            return json.loads(blob)

    if obj_start != -1:
        blob = _slice_balanced_json(t, obj_start, "{", "}")
        if blob:
            return json.loads(blob)

    raise ValueError("Model response did not contain a parseable JSON value")


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
    examples_blob = _format_embedded_prediction_examples()
    return f"""You are a SOC analyst assistant. Below are aggregated detection incidents produced by deterministic rules (each item may include rule_id, source_ip, username, time range, indicators).

IMPORTANT: If the aggregated incidents list is empty OR if you conclude there is no attack, DO NOT invent anything. In that case, return an EMPTY response (no JSON, no text).

You must return a LIST of detections (JSON array). Include one detection per distinct attack type you believe is present (you may return 1..N items).

Each detection.detection.attack_type MUST be exactly one value from this closed list (copy the string verbatim):
{types_list}

If signals conflict, include multiple detections if justified (e.g., SSH brute force AND credential stuffing).

Return ONLY valid JSON (no markdown, no commentary) with exactly this shape:
[
  {{
    "challenge_id": "<string; always use the initial intrusion vector attack_type, even when post-compromise activity is folded in>",
    "severity": "<exactly one of: low | medium | high | critical — standard SIEM-style urgency>",
    "alert_summary": "<string: short executive summary for alert queues and dashboards (1–3 sentences, plain text)>",
    "detection": {{
      "attack_type": "<one of the allowed values>",
      "attacker_ips": ["<ipv4 strings, deduplicated, empty if unknown>"],
      "victim_accounts": ["<account names involved as victims or targets, deduplicated>"],
      "attack_start_time": "<ISO 8601 UTC ending with Z>",
      "attack_end_time": "<ISO 8601 UTC ending with Z>",
      "indicators": {{ }}
    }},
    "detection_time_seconds": {detection_time_seconds},
    "confidence": {{
      "challenge_id": <float 0.0-1.0: your confidence in challenge_id>,
      "severity": <float 0.0-1.0: confidence in the severity assignment>,
      "alert_summary": <float 0.0-1.0: confidence that the summary accurately reflects the incident>,
      "remediation_proposal": <float 0.0-1.0: confidence that the remediation steps are appropriate and actionable for this incident>,
      "detection": {{
        "attack_type": <float 0.0-1.0>,
        "attacker_ips": [<float 0.0-1.0 per entry, same length and order as detection.attacker_ips>],
        "victim_accounts": [<float 0.0-1.0 per entry, same length and order as detection.victim_accounts>],
        "attack_start_time": <float 0.0-1.0>,
        "attack_end_time": <float 0.0-1.0>,
        "indicators": <float 0.0-1.0: confidence in the indicators object as a whole>
      }},
      "detection_time_seconds": <float 0.0-1.0: usually 1.0 if fixed by pipeline, lower if inferred>
    }},
    "reasons": {{
      "challenge_id": "<string: detailed justification for challenge_id>",
      "severity": "<string: why this severity tier (impact, likelihood, asset criticality from incidents)>",
      "alert_summary": "<string: how you distilled the summary from the evidence>",
      "remediation_proposal": "<string: why these remediation actions were chosen and how they map to the observed attack>",
      "detection": {{
        "attack_type": "<string: detailed justification for attack_type>",
        "attacker_ips": ["<string: detailed justification for EACH IP, same length and order as detection.attacker_ips>"],
        "victim_accounts": ["<string: detailed justification for EACH account, same length and order as detection.victim_accounts>"],
        "attack_start_time": "<string: how you derived or bounded this timestamp>",
        "attack_end_time": "<string: how you derived or bounded this timestamp>",
        "indicators": "<string: detailed explanation of what you put in indicators and why>"
      }},
      "detection_time_seconds": "<string: meaning of this field for this detection (e.g. pipeline constant vs inferred)>"
    }},
    "exhaustive_analysis": "<string: exhaustive narrative of what happened — full situation, timeline, involved actors (sources, targets), technical observations, rule firings, and how conclusions follow from the aggregated incidents. This is the main human-readable incident story; be thorough and structured (paragraphs or bullet-style sentences allowed as plain text inside the string).>",
    "remediation_proposal": "<string: prioritized operational remediation for SOC/IR — concrete actions (contain, eradicate, recover) adapted to this attack_type and evidence; plain text, may use short numbered lines inside the string; MUST be distinct from exhaustive_analysis (here: what to do next, not what happened)>"
  }}
]

Reference examples (illustrative JSON only — IPs and text are fictional; your response MUST be grounded in the real aggregated incidents listed later, not copied from these examples):

{examples_blob}

Rules:
- attacker_ips: derive from incident source_ip fields when present; omit empty strings.
- victim_accounts: for credential_stuffing, use ONLY the usernames from CREDENTIAL_STUFFING_SUCCESS incidents (indicators.compromised_usernames) — targeted-but-not-compromised accounts (CREDENTIAL_STUFFING_USER_TARGETED) are NOT victims. For other attack types, use usernames that appear as confirmed targets.
- Timestamps: merge overlapping incidents; if unclear use the widest reasonable span from the incidents or empty-window fallback "1970-01-01T00:00:00Z".
- indicators: compact dict summarizing key signals (rule_ids, counts, distinct_usernames, etc.).
- Attack chain: when multiple incidents share the same attacker IPs and form a logical progression (e.g. initial access → execution → exfiltration), emit a SINGLE detection for the dominant attack type and fold the secondary signals into its indicators rather than emitting separate detections.
- severity: MUST be one of low, medium, high, critical (lowercase English tokens). Map impact and likelihood to the tier used in your SOC (e.g. widespread exfiltration or critical asset → high/critical).
- alert_summary: concise and actionable; no duplicate of exhaustive_analysis — a scannable headline.
- confidence: every value must be a number in [0.0, 1.0]. For empty attacker_ips / victim_accounts, use empty arrays [] for the corresponding confidence lists. Higher means more certain that the paired field value is correct and well-supported by the incidents.
- reasons: parallel narrative to detection + top-level fields. Use clear, detailed natural language (English or French is fine). For empty attacker_ips / victim_accounts, use [] for the string arrays. Each string should explain why the paired value was chosen, citing signals from the aggregated incidents where possible.
- exhaustive_analysis: single string covering the entire incident story for this detection (not a duplicate of reasons field-by-field — synthesize timeline, impact, and reasoning). Must be exhaustive relative to the evidence in the aggregated incidents.
- remediation_proposal: actionable remediation only (blocks, patches, MFA, WAF rules, account resets, network isolation, etc. as relevant). Do not repeat the narrative from exhaustive_analysis; focus on what operators should execute next.

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
    inline_aws_credentials: Mapping[str, str] | None = None,
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
        model_id=model_id,
        max_tokens=max_tokens,
        profile_name=profile_name,
        inline_credentials=dict(inline_aws_credentials) if inline_aws_credentials else None,
    )
    return _extract_json_value(raw)
