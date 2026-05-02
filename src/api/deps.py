"""Client S3 avec profil AWS optionnel."""

from __future__ import annotations

from typing import Any

import boto3

from api import config


def s3_client() -> Any:
    session = (
        boto3.Session(profile_name=config.AWS_PROFILE)
        if config.AWS_PROFILE
        else boto3.Session()
    )
    return session.client("s3", region_name=config.REGION)
