"""Clients et dépendances réutilisables pour les endpoints."""

from __future__ import annotations

import os
from typing import Any

import boto3

from backend.api import config


def s3_client() -> Any:
    """Client S3 : si ``AWS_ACCESS_KEY_ID`` + ``AWS_SECRET_ACCESS_KEY`` sont dans l'environnement
    (ex. ``docker run -e AWS_ACCESS_KEY_ID …``), ils sont utilisés explicitement ; sinon chaîne
    boto3 par défaut (rôle instance, ``~/.aws``, …).
    """
    ak = (os.getenv("AWS_ACCESS_KEY_ID") or "").strip()
    sk = (os.getenv("AWS_SECRET_ACCESS_KEY") or "").strip()
    st = (os.getenv("AWS_SESSION_TOKEN") or "").strip() or None
    kwargs: dict[str, Any] = {"region_name": config.REGION}
    if ak and sk:
        kwargs["aws_access_key_id"] = ak
        kwargs["aws_secret_access_key"] = sk
        if st:
            kwargs["aws_session_token"] = st
    return boto3.client("s3", **kwargs)
