"""Client AWS minimal : une ``boto3.Session`` avec profil ou identifiants explicites."""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

import boto3
from botocore.config import Config

_BEDROCK_CONFIG = Config(retries={"max_attempts": 5, "mode": "standard"})


class AwsClient:
    """Session boto3 pour la région donnée.

    - ``credentials`` : ``aws_access_key_id``, ``aws_secret_access_key``, ``aws_session_token`` (optionnel).
    - Sinon ``profile_name`` (ex. profil SSO).
    - Sinon chaîne d’identifiants par défaut de boto3 (rôle instance, variables d’environnement, etc.).
    """

    def __init__(
        self,
        *,
        region_name: str = "eu-west-3",
        profile_name: str | None = None,
        credentials: Mapping[str, str] | None = None,
    ) -> None:
        self._region_name = (region_name or "eu-west-3").strip() or "eu-west-3"
        self._profile_name = (profile_name or "").strip() or None
        self._credentials: dict[str, str] | None = None
        if credentials:
            ak = (credentials.get("aws_access_key_id") or "").strip()
            sk = (credentials.get("aws_secret_access_key") or "").strip()
            if ak and sk:
                d: dict[str, str] = {"aws_access_key_id": ak, "aws_secret_access_key": sk}
                st = (credentials.get("aws_session_token") or "").strip()
                if st:
                    d["aws_session_token"] = st
                self._credentials = d

    def session(self) -> boto3.Session:
        kw: dict[str, Any] = {"region_name": self._region_name}
        if self._credentials:
            kw.update(self._credentials)
        elif self._profile_name:
            kw["profile_name"] = self._profile_name
        return boto3.Session(**kw)

    def client(self, service_name: str, **kwargs: Any) -> Any:
        return self.session().client(service_name, **kwargs)

    def bedrock_runtime(self) -> Any:
        return self.client("bedrock-runtime", config=_BEDROCK_CONFIG)

    @classmethod
    def for_env(cls, *, region_name: str | None = None) -> AwsClient:
        """Construit un client à partir de l’environnement courant (clés explicites ou ``AWS_PROFILE``)."""
        reg = (
            (region_name or "").strip()
            or os.getenv("AWS_REGION", "").strip()
            or os.getenv("AWS_DEFAULT_REGION", "").strip()
            or "eu-west-3"
        )
        ak = (os.getenv("AWS_ACCESS_KEY_ID") or "").strip()
        sk = (os.getenv("AWS_SECRET_ACCESS_KEY") or "").strip()
        if ak and sk:
            creds: dict[str, str] = {"aws_access_key_id": ak, "aws_secret_access_key": sk}
            st = (os.getenv("AWS_SESSION_TOKEN") or "").strip()
            if st:
                creds["aws_session_token"] = st
            return cls(region_name=reg, credentials=creds)
        prof = (os.getenv("AWS_PROFILE") or "").strip() or None
        return cls(region_name=reg, profile_name=prof)
