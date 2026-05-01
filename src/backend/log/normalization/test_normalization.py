import gzip
import json
import os
import sys
from pathlib import Path

import boto3

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))  # adds /.../src
from backend.log.normalization.normalize import normalize  # noqa: E402


# CREDS:
# - Either run `aws configure sso` then `aws sso login --profile <name>` and set:
#     export AWS_PROFILE="<name>"
# - Or export AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_SESSION_TOKEN.

BUCKET = os.getenv("S3_BUCKET", "clair-obscure-raw-logs")
PREFIX = os.getenv("S3_PREFIX", "raw/opensearch/logs-raw/")
REGION = os.getenv("AWS_DEFAULT_REGION", "eu-west-3")
PROFILE = os.getenv("AWS_PROFILE")

N_BATCHES = 1


session = boto3.Session(profile_name=PROFILE, region_name=REGION) if PROFILE else boto3.Session(region_name=REGION)
s3 = session.client("s3")

resp = s3.list_objects_v2(Bucket=BUCKET, Prefix=PREFIX)
objs = resp.get("Contents", [])
objs.sort(key=lambda o: o["LastModified"], reverse=True)
latest = objs[:N_BATCHES]

print(f"Found {len(latest)} objects (latest {N_BATCHES}).")

total = 0
for o in latest:
    key = o["Key"]
    body = s3.get_object(Bucket=BUCKET, Key=key)["Body"].read()
    for i, line in enumerate(gzip.decompress(body).splitlines()):
        rec = json.loads(line)
        raw = rec.get("_source", rec)
        norm = normalize(raw, {"raw_id": rec.get("_id", ""), "s3_key": key, "line": i})
        print(norm)
        total += 1
        if total == 1:
            print("Example normalized event:")
            print(json.dumps(norm, ensure_ascii=False))

print(f"Normalized events: {total}")
