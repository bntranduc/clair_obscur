#!/usr/bin/env python3
import argparse
import json
import os
from typing import Any
from opensearchpy import OpenSearch

PAGE_SIZE = 10_000


def env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def build_client() -> OpenSearch:
    host = os.getenv(
        "OPENSEARCH_HOST",
        "search-hackathon-cnd-finale-gqskvwuwmmhjxrfsumj7wqlfji.eu-west-3.es.amazonaws.com")
    port = int(os.getenv("OPENSEARCH_PORT", "443"))
    user = os.getenv("OPENSEARCH_USER", "etudiant")
    password = os.getenv("OPENSEARCH_PASSWORD", "Hackathon2026!Read")
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


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export ALL OpenSearch logs between two timestamps into a JSON file."
    )
    parser.add_argument(
        "--index",
        default=os.getenv("OPENSEARCH_INDEX", "logs-raw"),
        help="OpenSearch index name (default: OPENSEARCH_INDEX or logs-raw).",
    )
    parser.add_argument(
        "--timestamp-field",
        default=os.getenv("OPENSEARCH_TIMESTAMP_FIELD", "timestamp"),
        help="Field used for sorting (default: timestamp).",
    )
    parser.add_argument(
        "--start",
        default=os.getenv("OPENSEARCH_START"),
        required=True,
        help="Start timestamp (inclusive), e.g. 2026-04-01T00:00:00Z",
    )
    parser.add_argument(
        "--end",
        default=os.getenv("OPENSEARCH_END"),
        required=True,
        help="End timestamp (inclusive), e.g. 2026-04-25T23:59:59Z",
    )
    parser.add_argument(
        "-o",
        "--out",
        default="opensearch_range_logs.json",
        help="Output JSON file (default: opensearch_range_logs.json).",
    )
    args = parser.parse_args()

    client = build_client()
    search_after: list[Any] | None = None
    total = 0

    range_filter = {"gte": args.start, "lte": args.end}

    # Stream-write to avoid loading millions of docs in RAM
    with open(args.out, "w", encoding="utf-8") as f:
        f.write("[\n")
        first = True

        while True:
            query: dict[str, Any] = {
                "size": PAGE_SIZE,
                "sort": [
                    {args.timestamp_field: {"order": "desc"}},
                    {"_id": {"order": "desc"}},
                ],
                "query": {"range": {args.timestamp_field: range_filter}},
            }

            if search_after is not None:
                query["search_after"] = search_after

            resp = client.search(index=args.index, body=query)
            page_hits = resp.get("hits", {}).get("hits", [])

            if not page_hits:
                break

            for hit in page_hits:
                if not first:
                    f.write(",\n")
                json.dump(hit, f, ensure_ascii=False)
                first = False

            total += len(page_hits)
            print(f"  {total} logs exported so far...", end="\r")

            search_after = page_hits[-1].get("sort")
            if not search_after:
                break

        f.write("\n]")

    print(f"\n✅ Exported {total} logs to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
