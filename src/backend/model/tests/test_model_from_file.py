import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))  # adds /.../src

from backend.log.normalization.normalize import normalize  # noqa: E402
from backend.model.rules.aggregate_signals import aggregate_signals  # noqa: E402
from backend.model.rules.rules_window import detect_signals_window_1h  # noqa: E402
from backend.model import DEFAULT_ALLOWED_ATTACK_TYPES, predict_submission_from_incidents  # noqa: E402


DATASET = (
    Path(__file__).resolve().parents[4]
    / "datasets/dataset_test/attacks/opensearch_range_logs_ssh_bruteforce_plus2h.json"
)


def main() -> int:
    path = str(DATASET)
    data = json.loads(DATASET.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise SystemExit("Expected a JSON array of logs")

    events: list[dict[str, Any]] = []
    for i, rec in enumerate(data):
        raw = rec.get("_source", rec) if isinstance(rec, dict) else rec
        raw_id = rec.get("_id", "") if isinstance(rec, dict) else ""
        events.append(normalize(raw, {"raw_id": raw_id, "file": path, "line": i}))

    signals = detect_signals_window_1h(events)
    incidents = aggregate_signals(signals)
    if not incidents:
        return 0

    pred = predict_submission_from_incidents(incidents, allowed_attack_types=DEFAULT_ALLOWED_ATTACK_TYPES)
    print(json.dumps(pred, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
