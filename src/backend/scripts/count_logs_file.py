#!/usr/bin/env python3
"""Compte le nombre de logs dans un fichier .jsonl du bucket S3."""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import boto3

ENV_FILE = Path(__file__).parent.parent / ".env.aws"
load_dotenv(ENV_FILE, override=True)

BUCKET = os.environ["S3_BUCKET"]
REGION = os.environ.get("AWS_REGION", "eu-west-3")

s3 = boto3.client(
    "s3",
    region_name=REGION,
    aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
    aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
    aws_session_token=os.environ.get("AWS_SESSION_TOKEN"),
)


def count_logs_in_file(key: str) -> int:
    body = s3.get_object(Bucket=BUCKET, Key=key)["Body"].read().decode()
    return sum(1 for line in body.splitlines() if line.strip())


def main():
    if len(sys.argv) < 2:
        print("Usage: uv run --with boto3 --with python-dotenv scripts/count_logs_file.py <s3-key>")
        print("Ex:    scripts/count_logs_file.py logs-raw/year=2026/month=04/day=20/<uuid>.jsonl")
        sys.exit(1)

    key = sys.argv[1]
    count = count_logs_in_file(key)
    print(f"Fichier : s3://{BUCKET}/{key}")
    print(f"Logs    : {count}")


if __name__ == "__main__":
    main()
