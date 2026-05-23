"""Lecture locale des logs depuis un répertoire de fichiers JSONL (alternative à S3)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

from backend.log.normalization.normalize import normalize
from backend.log.normalization.types import NormalizedEvent


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
