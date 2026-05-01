#!/usr/bin/env python3
"""Liste et affiche les prédictions JSON dans model-attacks-predictions.

  LIST_ONLY=1     n'affiche que clé + taille (pas le corps)
  BODY_CHARS=8000 longueur max du JSON affiché par objet (défaut 8000)
"""

from __future__ import annotations

import json
import os

import boto3

BUCKET = os.getenv("S3_BUCKET", "model-attacks-predictions").strip()
PREFIX = os.getenv("S3_PREFIX", "predictions/").strip()
REGION = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "eu-west-3"))
MAX_KEYS = int(os.getenv("MAX_KEYS", "50"))
LIST_ONLY = os.getenv("LIST_ONLY", "0").strip() == "1"
BODY_CHARS = int(os.getenv("BODY_CHARS", "8000"))


def main() -> None:
    s3 = boto3.client("s3", region_name=REGION)
    kwargs: dict = {"Bucket": BUCKET, "Prefix": PREFIX, "MaxKeys": min(MAX_KEYS, 1000)}
    n = 0
    while True:
        resp = s3.list_objects_v2(**kwargs)
        for obj in resp.get("Contents", []):
            key = obj["Key"]
            print(f"{key}\t{obj['Size']} B")
            if not LIST_ONLY:
                raw = s3.get_object(Bucket=BUCKET, Key=key)["Body"].read().decode("utf-8", errors="replace")
                try:
                    pretty = json.dumps(json.loads(raw), indent=2, ensure_ascii=False)
                except json.JSONDecodeError:
                    pretty = raw
                tail = "…" if len(pretty) > BODY_CHARS else ""
                print(pretty[:BODY_CHARS] + tail)
                print("---")
            n += 1
            if n >= MAX_KEYS:
                return
        if not resp.get("IsTruncated"):
            break
        kwargs["ContinuationToken"] = resp["NextContinuationToken"]


if __name__ == "__main__":
    main()
