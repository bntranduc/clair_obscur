import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))  # adds /.../src
from backend.log.normalization.normalize import normalize  # noqa: E402
from backend.model.rules.aggregate_signals import aggregate_signals  # noqa: E402
from backend.model.rules.rules_window import detect_signals_window_1h  # noqa: E402


WINDOW_SECONDS = 18_000
STRIDE = int(sys.argv[2]) if len(sys.argv) > 2 else 500  # apply rules every N events


def _to_dt(ts: str) -> datetime:
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    return datetime.fromisoformat(ts).astimezone(timezone.utc)


def _load_events_from_file(path: str) -> list[dict]:
    data = json.load(open(path, "r", encoding="utf-8"))
    events = []
    for i, rec in enumerate(data):
        raw = rec.get("_source", rec)
        ev = normalize(raw, {"raw_id": rec.get("_id", ""), "s3_key": path, "line": i})
        if ev.get("timestamp"):
            events.append(ev)
    return events


input_path = "/home/bao/clair_obscur/datasets/dataset_test/attacks/opensearch_range_logs_ssh_bruteforce_plus2h.json"
events = _load_events_from_file(input_path)

events.sort(key=lambda e: e["timestamp"])
print(f"Loaded+normalized events: {len(events)}")

# Sliding window (two-pointer)
signals_total = 0
start = 0

all_sigs = []

for idx in range(0, len(events), STRIDE):
    end_ts = events[idx]["timestamp"]
    end_dt = _to_dt(end_ts)

    while start < idx and (end_dt - _to_dt(events[start]["timestamp"])).total_seconds() > WINDOW_SECONDS:
        start += 1

    window_events = events[start : idx + 1]
    sigs = detect_signals_window_1h(window_events)
    signals_total += len(sigs)
    all_sigs.extend(sigs)

incidents = aggregate_signals(all_sigs)
for inc in incidents:
    print(json.dumps(inc, ensure_ascii=False))
print(f"Done. Total signals emitted (summed over strides): {signals_total}")
