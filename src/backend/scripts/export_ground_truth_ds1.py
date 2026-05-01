#!/usr/bin/env python3
"""
Export the latest ground truth documents for Dataset 1 from OpenSearch.

Index pattern (given by organizers): ground-truth-ds1

Usage:
  python3 export_ground_truth_ds1.py -o ground_truth_ds1_last_10000.json
  python3 export_ground_truth_ds1.py --size 10000 --out ground_truth_ds1_last_10000.json

Notes:
  - Uses search_after pagination (safe above 10k if needed).
  - Sorts primarily by `timestamp` when present, otherwise falls back to `_id`.
"""

import argparse
import json
import os
from typing import Any, Optional

from opensearchpy import OpenSearch


DEFAULT_INDEX = "ground-truth-ds1"
DEFAULT_EXPORT_SIZE = 10_000
PAGE_SIZE = 10_000


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


def detect_timestamp_field(client: OpenSearch, index: str) -> Optional[str]:
    """
    Try to detect a usable timestamp field in the index mapping.
    We'll prefer 'timestamp' or '@timestamp' if present.
    """
    try:
        mapping = client.indices.get_mapping(index=index)
    except Exception:
        return None

    # mapping shape: {index: {mappings: {properties: {...}}}}
    idx = next(iter(mapping.values()), {})
    props = (
        idx.get("mappings", {}).get("properties", {})
        if isinstance(idx, dict)
        else {}
    )
    if "timestamp" in props:
        return "timestamp"
    if "@timestamp" in props:
        return "@timestamp"
    return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export the N latest documents from OpenSearch ground truth index (Dataset 1)."
    )
    parser.add_argument(
        "--index",
        default=os.getenv("OPENSEARCH_GT_INDEX", DEFAULT_INDEX),
        help=f"OpenSearch index name (default: {DEFAULT_INDEX}).",
    )
    parser.add_argument(
        "--size",
        type=int,
        default=int(os.getenv("OPENSEARCH_GT_EXPORT_SIZE", str(DEFAULT_EXPORT_SIZE))),
        help=f"Number of latest documents to export (default: {DEFAULT_EXPORT_SIZE}).",
    )
    parser.add_argument(
        "-o",
        "--out",
        default="ground_truth_ds1_last_10000.json",
        help="Output JSON file (default: ground_truth_ds1_last_10000.json).",
    )
    args = parser.parse_args()

    if args.size <= 0:
        raise SystemExit("--size must be > 0")

    client = build_client()
    ts_field = detect_timestamp_field(client, args.index)

    hits: list[dict[str, Any]] = []
    search_after: list[Any] | None = None

    while len(hits) < args.size:
        remaining = args.size - len(hits)
        page_size = min(PAGE_SIZE, remaining)

        sort = []
        if ts_field:
            sort.append({ts_field: {"order": "desc"}})
        # Always add a tiebreaker.
        sort.append({"_id": {"order": "desc"}})

        query: dict[str, Any] = {
            "size": page_size,
            "sort": sort,
            "query": {"match_all": {}},
        }
        if search_after is not None:
            query["search_after"] = search_after

        resp = client.search(index=args.index, body=query)
        page_hits = resp.get("hits", {}).get("hits", [])
        if not page_hits:
            break

        hits.extend(page_hits)
        search_after = page_hits[-1].get("sort")
        if not search_after:
            break

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(hits, f, indent=2, ensure_ascii=False)

    print(
        f"✅ Exported {len(hits)} ground truth docs from index={args.index}"
        f"{' (sorted by ' + ts_field + ')' if ts_field else ' (sorted by _id)'}"
        f" to {args.out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

