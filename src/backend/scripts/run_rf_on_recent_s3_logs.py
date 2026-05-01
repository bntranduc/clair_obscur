#!/usr/bin/env python3
"""
Télécharge les N derniers logs depuis S3 (fichiers les plus récents puis lignes de fin),
normalise en ``NormalizedEvent``, applique ``AttackPredictor``.

Variables d'environnement :
  S3_BUCKET           défaut: clair-obscure-raw-logs
  S3_PREFIX           défaut: logs-raw/ (ex. raw/opensearch/logs-raw/)
  AWS_REGION          défaut: eu-west-3
  RF_MODEL_DIR        défaut: attack_predictor/predictors/

Credentials : chaîne par défaut boto3 (profil SSO, IAM, etc.).
"""

from __future__ import annotations

import argparse
import gzip
import json
import os
import sys
from collections import Counter
from pathlib import Path

_ROOT_SRC = Path(__file__).resolve().parents[2]
if str(_ROOT_SRC) not in sys.path:
    sys.path.insert(0, str(_ROOT_SRC))

import boto3  # noqa: E402

from backend.log.normalization.normalize import normalize  # noqa: E402
from backend.model.attack_predictor import AttackPredictor  # noqa: E402
from backend.model.attack_predictor.paths import DEFAULT_LOCAL_MODEL_DIR  # noqa: E402


def _decode_object(body: bytes, key: str) -> str:
    if key.endswith(".gz"):
        return gzip.decompress(body).decode("utf-8", errors="replace")
    return body.decode("utf-8", errors="replace")


def _iter_sources_from_jsonl(text: str) -> list[dict]:
    out: list[dict] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        raw = rec.get("_source", rec)
        if isinstance(raw, dict):
            out.append(raw)
    return out


def list_objects_newest_first(s3, bucket: str, prefix: str) -> list[dict]:
    paginator = s3.get_paginator("list_objects_v2")
    objs: list[dict] = []
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        objs.extend(page.get("Contents", []))
    objs.sort(key=lambda o: o["LastModified"], reverse=True)
    return [o for o in objs if not o["Key"].endswith("/")]


def fetch_last_n_sources(s3, bucket: str, prefix: str, n: int) -> list[tuple[dict, str]]:
    """Return up to ``n`` (source dict, s3_key) newest-first temporal-ish."""
    files = list_objects_newest_first(s3, bucket, prefix)
    collected: list[tuple[dict, str]] = []
    for obj in files:
        key = obj["Key"]
        try:
            body = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
            text = _decode_object(body, key)
        except Exception as e:
            print(f"WARN skip {key}: {e}", file=sys.stderr)
            continue
        sources = _iter_sources_from_jsonl(text)
        for raw in reversed(sources):
            collected.append((raw, key))
            if len(collected) >= n:
                collected.reverse()
                return collected
    collected.reverse()
    return collected


def main() -> int:
    parser = argparse.ArgumentParser(description="Run RF attack predictor on recent S3 logs")
    parser.add_argument("--bucket", default=os.getenv("S3_BUCKET", "clair-obscure-raw-logs"))
    parser.add_argument("--prefix", default=os.getenv("S3_PREFIX", "logs-raw/"))
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument(
        "--model-dir",
        default=os.getenv("RF_MODEL_DIR", str(DEFAULT_LOCAL_MODEL_DIR.resolve())),
    )
    parser.add_argument("--sample-json", type=int, default=0, help="Print first N predictions as JSON lines")
    args = parser.parse_args()

    region = os.getenv("AWS_DEFAULT_REGION", os.getenv("AWS_REGION", "eu-west-3"))
    session = boto3.Session(region_name=region)
    s3 = session.client("s3")

    try:
        rows = fetch_last_n_sources(s3, args.bucket, args.prefix, args.limit)
    except Exception as e:
        print(f"S3 error: {e}", file=sys.stderr)
        return 1

    if not rows:
        print("No log records found (vérifie S3_PREFIX et que des fichiers existent).", file=sys.stderr)
        return 2

    pred_path = Path(args.model_dir)
    if not (pred_path / "model.joblib").is_file():
        print(
            f"Missing model under {args.model_dir}. Train first:\n"
            "PYTHONPATH=src python3 -m backend.model.attack_predictor.train ...",
            file=sys.stderr,
        )
        return 3

    predictor = AttackPredictor.load(pred_path)

    counts: Counter[str] = Counter()
    top_probs: list[float] = []

    for i, (raw, key) in enumerate(rows):
        ev = normalize(raw, {"s3_key": key, "line": i})
        out = predictor.predict_event(ev)
        lab = str(out["predicted_attack_type"])
        counts[lab] += 1
        top_probs.append(float(out["top_probability"]))
        if args.sample_json and i < args.sample_json:
            rec = {"index": i, "key": key, "prediction": out}
            print(json.dumps(rec, ensure_ascii=False))

    print(json.dumps({"records_scored": len(rows), "bucket": args.bucket, "prefix": args.prefix}, indent=2))
    print("predicted_attack_type counts:")
    for lab, c in counts.most_common():
        print(f"  {lab}: {c}")
    if top_probs:
        avg = sum(top_probs) / len(top_probs)
        print(f"mean top_probability: {avg:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
