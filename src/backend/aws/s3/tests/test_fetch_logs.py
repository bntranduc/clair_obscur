"""Appel test de ``fetch_all_normalized_logs`` (nécessite accès S3 + préfixe peuplé).

Exemple :
  cd repo && PYTHONPATH=src python3 src/backend/aws/s3/tests/test_fetch_logs.py
"""
from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[4]
_REPO = _SRC.parent
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from dotenv import load_dotenv  # noqa: E402

from backend.aws.s3.logs import fetch_all_normalized_logs  # noqa: E402


def main() -> int:
    load_dotenv(_REPO / ".env", override=True)
    events = fetch_all_normalized_logs()
    print(f"events: {len(events)}")
    if events:
        print("first:", events[0])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
