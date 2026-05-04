#!/usr/bin/env python3
"""500 derniers items pour un pk donné (même jour / même shard que ton import).

Identifiants AWS (ne pas mettre de secrets dans ce fichier) :
  - export AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=...
    (et AWS_SESSION_TOKEN=... si session STS)
  - ou export AWS_PROFILE=ton_profil  (après aws sso login / aws configure)
"""
from __future__ import annotations

import json
import os
import sys

import boto3

REGION = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "eu-west-3"))
TABLE = os.getenv("DYNAMODB_TABLE", "normalized-logs")
PK = os.getenv("DYNAMODB_PK", "RAW#clair-obscure-raw-logs#D#2026-01-12")


def _aws_session() -> boto3.Session:
    ak = (os.getenv("AWS_ACCESS_KEY_ID") or "").strip()
    sk = (os.getenv("AWS_SECRET_ACCESS_KEY") or "").strip()
    st = (os.getenv("AWS_SESSION_TOKEN") or "").strip() or None
    profile = (os.getenv("AWS_PROFILE") or "").strip() or None
    if ak and sk:
        return boto3.Session(
            aws_access_key_id=ak,
            aws_secret_access_key=sk,
            aws_session_token=st,
            region_name=REGION,
        )
    if profile:
        return boto3.Session(profile_name=profile, region_name=REGION)
    return boto3.Session(region_name=REGION)


table = _aws_session().resource("dynamodb", region_name=REGION).Table(TABLE)
resp = table.query(
    KeyConditionExpression="pk = :p",
    ExpressionAttributeValues={":p": PK},
    ScanIndexForward=False,
    Limit=500,
)

print(json.dumps(resp["Items"], indent=2, ensure_ascii=False, default=str))
print(f"\nCount: {len(resp['Items'])}", file=sys.stderr)
