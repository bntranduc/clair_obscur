import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from dotenv import load_dotenv  # noqa: E402

from backend.log.normalization.normalize import normalize  # noqa: E402
from backend.model.predict import predict_alerts  # noqa: E402

_ROOT = str(Path(__file__).resolve().parents[4])
_DATA = f"{_ROOT}/datasets/dataset_test/attacks/opensearch_range_logs_ssh_bruteforce_plus2h.json"

# Charge AWS_PROFILE, BEDROCK_* depuis la racine du repo — pas de clés AWS requises (SSO + aws sso login).
load_dotenv(f"{_ROOT}/.env", override=True)


def main() -> int:
    with open(_DATA, encoding="utf-8") as f:
        rows = json.load(f)
    if not isinstance(rows, list):
        raise SystemExit("expected JSON array")

    events = []
    for i, rec in enumerate(rows):
        raw = rec.get("_source", rec) if isinstance(rec, dict) else rec
        rid = rec.get("_id", "") if isinstance(rec, dict) else ""
        events.append(normalize(raw, {"raw_id": rid, "file": _DATA, "line": i}))

    alerts = predict_alerts(events)
    print(json.dumps(alerts, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
