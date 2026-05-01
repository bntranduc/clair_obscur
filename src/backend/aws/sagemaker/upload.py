"""Upload ``model.tar.gz`` (or any file) to S3."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import boto3


def upload_file(
    local_path: Path | str,
    *,
    bucket: str,
    key: str,
    region: str | None = None,
    extra_args: dict[str, Any] | None = None,
) -> str:
    """Upload ``local_path`` to ``s3://bucket/key``. Returns the S3 URI."""
    path = Path(local_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    session = boto3.Session(region_name=region) if region else boto3.Session()
    client = session.client("s3")
    client.upload_file(str(path), bucket, key, ExtraArgs=extra_args or {})
    return f"s3://{bucket}/{key}"
