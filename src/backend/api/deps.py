"""Clients et dépendances réutilisables pour les endpoints."""

from __future__ import annotations

from typing import Any

import boto3

from backend.api import config


def s3_client() -> Any:
    return boto3.client("s3", region_name=config.REGION)
