#!/usr/bin/env python3
"""Liste (et optionnellement affiche un extrait) des objets S3 (buckets / préfixes via variables d’env).

Usage :
  python3 src/backend/scripts/test_s3_list.py
  python3 src/backend/scripts/test_s3_list.py --kind raw
  python3 src/backend/scripts/test_s3_list.py --kind preds --peek 1

Prérequis : identifiants AWS — profil CLI, variables d’environnement, ou fichier
``src/backend/.env.aws`` (comme ``check_s3_logs.py`` ; nécessite ``pip install python-dotenv``).
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parent.parent  # .../src/backend

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None  # type: ignore[misc, assignment]
else:
    for _env_name in (".env.aws", ".env"):
        _p = _BACKEND_DIR / _env_name
        if _p.is_file():
            load_dotenv(_p, override=True)
            print(f"(variables depuis {_p})", flush=True)
            break

import boto3  # noqa: E402

RAW_BUCKET = os.getenv("RAW_LOGS_BUCKET", "clair-obscure-raw-logs").strip()
RAW_PREFIX = os.getenv("RAW_LOGS_PREFIX", "raw/opensearch/logs-raw/").strip()
REGION = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "eu-west-3"))
PREDICTIONS_BUCKET = os.getenv("PREDICTIONS_BUCKET", "model-attacks-predictions-tmp").strip()
PREDICTIONS_BUCKET_TMP = os.getenv("PREDICTIONS_BUCKET_TMP", "model-attacks-predictions-tmp").strip()
PREDICTIONS_PREFIX = (
    os.getenv("PREDICTIONS_PREFIX", os.getenv("S3_PREFIX", "predictions/")).strip() or "predictions/"
)
if not PREDICTIONS_PREFIX.endswith("/"):
    PREDICTIONS_PREFIX += "/"


def _print_credential_help() -> None:
    env_aws = _BACKEND_DIR / ".env.aws"
    print(
        """
Aucune chaîne d’identifiants AWS n’est disponible pour boto3. Choisis une option :

  1) Profil SSO
       aws sso login --profile <nom>
       export AWS_PROFILE=<nom>

  2) Profil classique
       aws configure
       # ou export AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY [/ AWS_SESSION_TOKEN]

  3) Fichier (même convention que check_s3_logs.py)
       Crée : {env_path}
       avec au minimum AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION=eu-west-3
       (et AWS_SESSION_TOKEN si credentials temporaires).

  4) Dépendance pour le fichier .env
       pip install python-dotenv
""".format(env_path=env_aws),
        file=sys.stderr,
        flush=True,
    )


def _client():
    return boto3.client("s3", region_name=REGION)


def list_keys(bucket: str, prefix: str, max_keys: int) -> list[dict]:
    s3 = _client()
    out: list[dict] = []
    kwargs: dict = {"Bucket": bucket, "Prefix": prefix, "MaxKeys": min(max_keys, 1000)}
    while True:
        r = s3.list_objects_v2(**kwargs)
        for x in r.get("Contents") or []:
            out.append({"Key": x["Key"], "Size": x["Size"]})
            if len(out) >= max_keys:
                return out
        if not r.get("IsTruncated"):
            break
        kwargs["ContinuationToken"] = r["NextContinuationToken"]
    return out


def peek_object(bucket: str, key: str, max_chars: int) -> None:
    s3 = _client()
    body = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
    if key.endswith(".gz"):
        body = gzip.decompress(body)
    text = body.decode("utf-8", errors="replace")[:max_chars]
    print(f"\n--- extrait ({key}) ---\n{text}")
    if len(body) > max_chars:
        print(f"\n… tronqué après {max_chars} caractères …")


def main() -> int:
    p = argparse.ArgumentParser(description="Test list / lecture S3")
    p.add_argument(
        "--kind",
        choices=("raw", "preds", "preds_tmp"),
        default="raw",
        help="raw=logs OpenSearch gzip ; preds / preds_tmp=buckets prédictions",
    )
    p.add_argument("--max-keys", type=int, default=15, help="Nombre max d’objets listés")
    p.add_argument("--peek", type=int, default=0, help="Si >0, télécharge le 1er objet et affiche N caractères")
    args = p.parse_args()

    if args.kind == "raw":
        bucket, prefix = RAW_BUCKET, RAW_PREFIX
    elif args.kind == "preds":
        bucket, prefix = PREDICTIONS_BUCKET, PREDICTIONS_PREFIX
    else:
        bucket, prefix = PREDICTIONS_BUCKET_TMP, PREDICTIONS_PREFIX

    print(f"Région : {REGION}", flush=True)
    print(f"Bucket : {bucket}", flush=True)
    print(f"Préfixe: {prefix!r}\n", flush=True)

    try:
        keys = list_keys(bucket, prefix, args.max_keys)
    except Exception as e:
        print(f"ERREUR list_objects_v2: {e}", file=sys.stderr, flush=True)
        if "credential" in str(e).lower():
            _print_credential_help()
        return 1

    if not keys:
        print("(aucun objet sous ce préfixe — ou bucket vide / mauvais préfixe)")
        return 0

    for i, o in enumerate(keys, 1):
        print(f"{i:3}  {o['Size']:>10} B  {o['Key']}")

    if args.peek > 0 and keys:
        try:
            peek_object(bucket, keys[0]["Key"], args.peek)
        except Exception as e:
            print(f"ERREUR get_object: {e}", file=sys.stderr)
            return 1
        if keys[0]["Key"].endswith(".json") or "predictions/" in keys[0]["Key"]:
            try:
                full = _client().get_object(Bucket=bucket, Key=keys[0]["Key"])["Body"].read()
                if keys[0]["Key"].endswith(".gz"):
                    full = gzip.decompress(full)
                data = json.loads(full.decode("utf-8"))
                n = len(data["alerts"]) if isinstance(data, dict) and isinstance(data.get("alerts"), list) else "?"
                print(f"\n(JSON) clés racine: {list(data) if isinstance(data, dict) else type(data)} — alerts: {n}")
            except Exception as ex:
                print(f"(aperçu JSON optionnel ignoré: {ex})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
