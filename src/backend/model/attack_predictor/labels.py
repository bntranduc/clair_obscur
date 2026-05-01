from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_attack_types_from_ground_truth(path: str | Path) -> list[str]:
    """Return sorted unique ``attack_type`` values from ``ground_truth_ds1``-style JSON."""
    p = Path(path)
    raw = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("Ground truth file must be a JSON array")
    types: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        src = item.get("_source")
        if isinstance(src, dict):
            at = src.get("attack_type") or src.get("challenge_id")
            if isinstance(at, str) and at.strip():
                types.add(at.strip())
    if not types:
        raise ValueError("No attack_type entries found in ground truth file")
    return sorted(types)


def validate_labels_against_ground_truth(
    labels_in_training: set[str],
    ground_truth_path: str | Path,
) -> None:
    allowed = set(load_attack_types_from_ground_truth(ground_truth_path))
    unknown = labels_in_training - allowed
    if unknown:
        raise ValueError(
            "Training contains attack_type values not present in ground truth: "
            + ", ".join(sorted(unknown))
        )
