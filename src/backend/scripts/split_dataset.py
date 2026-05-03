#!/usr/bin/env python3
"""
Split a large JSON-array dataset into overlapping time windows.

Usage:
  python split_dataset.py <input.json> --days 7 --overlap 24 --out-dir datasets/

Output files: <basename>_<start>_<end>.json  (e.g. opensearch_2026-01-14_2026-01-21.json)
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _ts(event: dict) -> datetime | None:
    src = event.get("_source") or event
    raw = src.get("timestamp") or src.get("@timestamp") or src.get("ts")
    if not raw:
        return None
    try:
        s = str(raw).rstrip("Z")
        dt = datetime.fromisoformat(s)
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
    except Exception:
        return None


def split(input_path: Path, days: int, overlap_hours: int, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = input_path.stem

    print(f"Loading {input_path} ...", flush=True)
    with open(input_path, encoding="utf-8") as f:
        data = json.load(f)
    print(f"  {len(data)} events loaded.", flush=True)

    dated = [(e, _ts(e)) for e in data]
    del data

    valid = [(e, dt) for e, dt in dated if dt is not None]
    invalid = [e for e, dt in dated if dt is None]
    del dated

    if not valid:
        print("No dated events found — nothing to split.", file=sys.stderr)
        return

    valid.sort(key=lambda x: x[1])
    t_min = valid[0][1].replace(hour=0, minute=0, second=0, microsecond=0)
    t_max = valid[-1][1]

    chunk_delta = timedelta(days=days)
    overlap_delta = timedelta(hours=overlap_hours)

    window_start = t_min
    chunks_written = 0
    while window_start <= t_max:
        window_end = window_start + chunk_delta
        low = window_start - overlap_delta
        high = window_end + overlap_delta

        chunk = [e for e, dt in valid if low <= dt < high]
        if invalid:
            chunk = invalid + chunk

        label_start = window_start.strftime("%Y-%m-%d")
        label_end = min(window_end, t_max + timedelta(seconds=1)).strftime("%Y-%m-%d")
        out_path = out_dir / f"{stem}_{label_start}_{label_end}.json"

        print(
            f"  Writing {out_path.name}: {len(chunk)} events "
            f"[{low.date()} → {high.date()}]",
            flush=True,
        )
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(chunk, f, ensure_ascii=False)

        chunks_written += 1
        window_start = window_end

    print(f"Done — {chunks_written} file(s) written in {out_dir}.", flush=True)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("input", type=Path, help="Input JSON array file")
    p.add_argument("--days", type=int, default=7, help="Window size in days (default: 7)")
    p.add_argument(
        "--overlap",
        type=int,
        default=24,
        metavar="HOURS",
        help="Overlap in hours on each side of the window (default: 24)",
    )
    p.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Output directory (default: same as input file)",
    )
    args = p.parse_args()

    if not args.input.exists():
        print(f"Error: file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    out_dir = args.out_dir or args.input.parent
    split(args.input, args.days, args.overlap, out_dir)


if __name__ == "__main__":
    main()
