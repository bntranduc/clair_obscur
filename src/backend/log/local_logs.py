"""Lecture locale des logs depuis un répertoire de fichiers JSONL (alternative à S3)."""

from __future__ import annotations

import base64
import json
import os
from collections.abc import Iterator
from pathlib import Path

from backend.log.normalization.normalize import normalize
from backend.log.normalization.types import NormalizedEvent


def repo_root() -> Path:
    # .../src/backend/log/local_logs.py → racine dépôt
    return Path(__file__).resolve().parents[3]


def resolve_local_logs_dir() -> Path | None:
    """Répertoire JSONL local si ``LOCAL_LOGS_DIR`` est défini et existe."""
    raw = (os.getenv("LOCAL_LOGS_DIR") or "").strip()
    if not raw:
        return None
    p = Path(raw)
    if not p.is_absolute():
        p = repo_root() / raw
    return p if p.is_dir() else None


def _encode_skip(skip: int) -> str:
    payload = json.dumps({"skip": skip}, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def _decode_skip(cursor: str | None) -> int:
    if not cursor or not str(cursor).strip():
        return 0
    c = str(cursor).strip()
    pad = (-len(c)) % 4
    raw = base64.urlsafe_b64decode(c.encode("ascii") + b"=" * pad)
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("start_key invalide")
    return max(0, int(data.get("skip", 0)))


def iter_normalized_events(
    local_dir: str | Path,
    *,
    newest_first: bool = True,
) -> Iterator[NormalizedEvent]:
    d = Path(local_dir)
    files = sorted(d.glob("*.jsonl"), key=lambda p: p.name, reverse=newest_first)
    for path in files:
        with path.open(encoding="utf-8", errors="replace") as fh:
            for n, line in enumerate(fh, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(row, dict):
                    continue
                src = row["_source"] if "_source" in row else row
                if not isinstance(src, dict):
                    continue
                yield normalize(src, raw_ref={"file": path.name, "line": n})


def fetch_normalized_page(
    *,
    skip: int = 0,
    limit: int = 50,
    local_dir: str | Path,
) -> tuple[list[NormalizedEvent], bool]:
    if skip < 0:
        skip = 0
    if limit < 1:
        limit = 1
    out: list[NormalizedEvent] = []
    has_more = False
    idx = -1
    for ev in iter_normalized_events(local_dir):
        idx += 1
        if idx < skip:
            continue
        if len(out) < limit:
            out.append(ev)
            continue
        has_more = True
        break
    return out, has_more


def fetch_normalized_page_cursor(
    *,
    limit: int = 50,
    start_key: str | None = None,
    local_dir: str | Path,
) -> tuple[list[NormalizedEvent], bool, str | None]:
    """Pagination compatible DynamoDB (``next_start_key`` = offset encodé)."""
    if limit < 1:
        limit = 1
    try:
        skip = _decode_skip(start_key)
    except (ValueError, json.JSONDecodeError, TypeError) as e:
        raise ValueError("start_key invalide") from e
    items, has_more = fetch_normalized_page(skip=skip, limit=limit, local_dir=local_dir)
    next_key = _encode_skip(skip + len(items)) if has_more else None
    return items, has_more, next_key


def load_events_up_to(local_dir: str | Path, *, max_items: int) -> list[dict]:
    """Charge jusqu’à ``max_items`` événements normalisés (dict) depuis un répertoire local."""
    cap = max(1, max_items)
    out: list[dict] = []
    for ev in iter_normalized_events(local_dir):
        out.append(dict(ev))
        if len(out) >= cap:
            break
    return out
