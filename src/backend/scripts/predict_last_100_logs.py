#!/usr/bin/env python3
"""
Fetch the 100 latest logs from OpenSearch (logs-raw) and call the local model API
(`POST /predict_attack`) to get an attack_type for each log.

Minimal deps:
  - opensearchpy (already used in repo scripts)
  - standard library for HTTP calls

Usage:
  python3 scripts/predict_last_100_logs.py
  python3 scripts/predict_last_100_logs.py --model-url http://localhost:9101/predict_attack
  python3 scripts/predict_last_100_logs.py --size 100 --index logs-raw
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any
from urllib.request import Request, urlopen

from opensearchpy import OpenSearch


def env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def build_client() -> OpenSearch:
    host = os.getenv(
        "OPENSEARCH_HOST",
        "search-hackathon-cnd-pytppy2betrf5qnoqporwcqqbm.eu-west-3.es.amazonaws.com",
    )
    port = int(os.getenv("OPENSEARCH_PORT", "443"))
    user = os.getenv("OPENSEARCH_USER", "etudiant")
    password = os.getenv("OPENSEARCH_PASSWORD", "HackathonCND2026!")

    use_ssl = env_bool("OPENSEARCH_USE_SSL", True)
    verify_certs = env_bool("OPENSEARCH_VERIFY_CERTS", True)
    http_auth = (user, password) if (user and password) else None

    return OpenSearch(
        hosts=[{"host": host, "port": port}],
        http_compress=True,
        http_auth=http_auth,
        use_ssl=use_ssl,
        verify_certs=verify_certs,
        ssl_assert_hostname=False,
        ssl_show_warn=False,
        timeout=60,
        max_retries=3,
        retry_on_timeout=True,
    )


def fetch_latest_logs(*, client: OpenSearch, index: str, size: int, timestamp_field: str) -> list[dict[str, Any]]:
    query: dict[str, Any] = {
        "size": size,
        "sort": [{timestamp_field: {"order": "desc"}}, {"_id": {"order": "desc"}}],
        "query": {"match_all": {}},
    }
    resp = client.search(index=index, body=query)
    return resp.get("hits", {}).get("hits", [])


def predict_one(*, model_url: str, log: dict[str, Any], timeout_s: int) -> str:
    body = json.dumps({"log": log}).encode("utf-8")
    req = Request(
        model_url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(req, timeout=timeout_s) as r:
        raw = r.read().decode("utf-8")
        data = json.loads(raw)
        return str(data.get("attack_type", "none"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Predict attack_type for latest OpenSearch logs.")
    parser.add_argument("--size", type=int, default=100, help="Number of logs to fetch (default: 100).")
    parser.add_argument("--index", default=os.getenv("OPENSEARCH_INDEX", "logs-raw"), help="OpenSearch index (default: logs-raw).")
    parser.add_argument("--timestamp-field", default=os.getenv("OPENSEARCH_TIMESTAMP_FIELD", "timestamp"), help="Sort field (default: timestamp).")
    parser.add_argument("--model-url", default=os.getenv("MODEL_URL", "http://localhost:9101/predict_attack"), help="Model endpoint URL.")
    parser.add_argument("--timeout", type=int, default=int(os.getenv("MODEL_TIMEOUT_S", "30")), help="HTTP timeout seconds (default: 30).")
    args = parser.parse_args()

    if args.size <= 0:
        print("--size must be > 0", file=sys.stderr)
        return 2

    client = build_client()
    hits = fetch_latest_logs(client=client, index=args.index, size=args.size, timestamp_field=args.timestamp_field)
    if not hits:
        print("No logs returned from OpenSearch.", file=sys.stderr)
        return 1

    counts: dict[str, int] = {}
    for h in hits:
        _id = h.get("_id")
        src = h.get("_source", {}) or {}
        label = predict_one(model_url=args.model_url, log=src, timeout_s=args.timeout)

        counts[label] = counts.get(label, 0) + 1
        print(f"{_id}\t{label}")

    print("\n--- summary ---")
    for k in sorted(counts.keys()):
        print(f"{k}: {counts[k]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

