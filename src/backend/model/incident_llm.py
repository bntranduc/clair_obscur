from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from backend.model.bedrock_client import MODEL_ID_DEFAULT, bedrock_converse_text
from backend.model.prompt.prompt import PREDICTION_PROMPT_TEMPLATE

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
    return PREDICTION_PROMPT_TEMPLATE.format(
        types_list=types_list,
        detection_time_seconds=detection_time_seconds,
        examples_blob=examples_blob,
        incidents_blob=incidents_blob,
    )


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
