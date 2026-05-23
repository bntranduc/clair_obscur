#!/usr/bin/env python3
"""
Télécharge tous les fichiers d'un dossier (prefix) S3 vers un répertoire local.

Usage :
  python download_s3_folder.py <bucket> <prefix> [options]

Exemples :
  python download_s3_folder.py clair-obscure-raw-logs raw/opensearch/logs-raw/dt=2026-01-01/
  python download_s3_folder.py clair-obscure-raw-logs raw/ --dest ./data --region eu-west-3

Variables d'environnement :
  AWS_ACCESS_KEY_ID     Credentials AWS
  AWS_SECRET_ACCESS_KEY Credentials AWS
  AWS_SESSION_TOKEN     Credentials AWS (session temporaire / SSO)
  AWS_DEFAULT_REGION    Région AWS (défaut : eu-west-3)
  AWS_PROFILE           Profil ~/.aws/credentials
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

# Charge le .env à la racine du repo s'il existe
try:
    from dotenv import load_dotenv
    _env = Path(__file__).resolve().parents[3] / ".env"
    if _env.exists():
        load_dotenv(_env)
except ImportError:
    pass


def _s3_client(region: str, profile: str | None):
    session = boto3.Session(profile_name=profile) if profile else boto3.Session()
    return session.client("s3", region_name=region)


def list_keys(s3, bucket: str, prefix: str) -> list[str]:
    keys: list[str] = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if not key.endswith("/"):  # skip "folder" placeholder objects
                keys.append(key)
    return keys


def download_all(
    bucket: str,
    prefix: str,
    dest: Path,
    *,
    region: str,
    profile: str | None,
    flat: bool,
    dry_run: bool,
) -> int:
    s3 = _s3_client(region, profile)

    print(f"Listage de s3://{bucket}/{prefix} ...")
    try:
        keys = list_keys(s3, bucket, prefix)
    except ClientError as e:
        print(f"Erreur S3 : {e}", file=sys.stderr)
        return 1

    if not keys:
        print("Aucun fichier trouvé.")
        return 0

    print(f"{len(keys)} fichier(s) trouvé(s).\n")
    dest.mkdir(parents=True, exist_ok=True)

    errors = 0
    for i, key in enumerate(keys, 1):
        if flat:
            local_path = dest / Path(key).name
        else:
            # reproduit l'arborescence S3 sous dest/, en retirant le prefix commun
            relative = key[len(prefix):].lstrip("/")
            local_path = dest / relative

        local_path.parent.mkdir(parents=True, exist_ok=True)

        label = f"[{i}/{len(keys)}] {key}"
        if dry_run:
            print(f"  (dry-run) {label} → {local_path}")
            continue

        if local_path.exists():
            print(f"  skip (existe) {label}")
            continue

        try:
            print(f"  ↓ {label}", end="", flush=True)
            s3.download_file(bucket, key, str(local_path))
            size = local_path.stat().st_size
            print(f"  ({size:,} o)")
        except ClientError as e:
            print(f"  ERREUR : {e}")
            errors += 1

    if dry_run:
        print(f"\n(dry-run) {len(keys)} fichier(s) seraient téléchargés dans {dest}")
    else:
        ok = len(keys) - errors
        print(f"\n{ok}/{len(keys)} fichier(s) téléchargé(s) dans {dest}")
        if errors:
            print(f"{errors} erreur(s).", file=sys.stderr)

    return 1 if errors else 0


def main() -> int:
    p = argparse.ArgumentParser(
        description="Télécharge tous les fichiers d'un prefix S3 vers un dossier local.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        "bucket",
        nargs="?",
        default=os.getenv("S3_BUCKET", "clair-obscure-raw-logs"),
        help="Nom du bucket S3 (défaut : $S3_BUCKET ou clair-obscure-raw-logs)",
    )
    p.add_argument("prefix", help="Prefix / dossier S3 (ex. raw/logs/dt=2026-01-01/)")
    p.add_argument(
        "--dest",
        type=Path,
        default=Path("./s3_download"),
        help="Dossier de destination local (défaut : ./s3_download)",
    )
    p.add_argument(
        "--region",
        default=os.getenv("AWS_DEFAULT_REGION", "eu-west-3"),
        help="Région AWS (défaut : eu-west-3)",
    )
    p.add_argument(
        "--profile",
        default=os.getenv("AWS_PROFILE"),
        help="Profil ~/.aws/credentials (défaut : $AWS_PROFILE)",
    )
    p.add_argument(
        "--flat",
        action="store_true",
        help="Télécharger tous les fichiers à plat dans --dest (ignore l'arborescence S3)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Lister les fichiers sans télécharger",
    )
    args = p.parse_args()

    return download_all(
        args.bucket,
        args.prefix,
        args.dest,
        region=args.region,
        profile=args.profile,
        flat=args.flat,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    raise SystemExit(main())
