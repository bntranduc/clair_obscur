"""Client OpenSearch partagé (même convention d’environnement que les scripts)."""

from __future__ import annotations

import os

from opensearchpy import OpenSearch


def env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def build_client() -> OpenSearch:
    host = os.getenv(
        "OPENSEARCH_HOST",
        "search-hackathon-cnd-pytppy2betrf5qnoqporwcqqbm.eu-west-3.es.amazonaws.com",
    )
    port = int(os.getenv("OPENSEARCH_PORT", "443"))
    user = os.getenv("OPENSEARCH_USER", "etudiant")
    password = os.getenv("OPENSEARCH_PASSWORD", "HackathonCND2026!")

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
        timeout=90,
        max_retries=2,
        retry_on_timeout=True,
    )
