#!/usr/bin/env python3
"""Point d'entrée CLI — logique dans ``backend.worker``."""
from __future__ import annotations

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
_SRC = _REPO / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from backend.worker.loop import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
