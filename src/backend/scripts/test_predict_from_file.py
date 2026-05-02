#!/usr/bin/env python3
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "src"))

from backend.model.predict import predict_alerts  # noqa: E402

# Chemin (relatif à la racine du repo ou absolu)
INPUT_JSON = _REPO / "datasets/dataset_test/attacks/opensearch_range_logs_ssh_bruteforce_plus2h.json"


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else INPUT_JSON
    if not path.is_file():
        path = _REPO / path
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict) and "events" in raw:
        events = raw["events"]
    elif isinstance(raw, list) and raw and isinstance(raw[0], dict) and "_source" in raw[0]:
        events = [h["_source"] for h in raw]
    else:
        events = raw
    out = predict_alerts(events)
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
