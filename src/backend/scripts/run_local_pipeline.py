#!/usr/bin/env python3
"""
Pipeline locale : fichier de logs raw → normalisation → règles → LLM → alertes.

Usage :
  python run_local_pipeline.py <logs_file> [options]

Le fichier peut être :
  - NDJSON (une entrée JSON par ligne)
  - JSON array
  - Format OpenSearch (_source wrappé ou non)
  - Gzip des formats ci-dessus (.gz)

Variables d'environnement optionnelles :
  BEDROCK_MODEL_ID      ID du modèle Bedrock (défaut : eu.anthropic.claude-opus-4-7)
  AWS_REGION            Région AWS (défaut : eu-west-3)
  AWS_ACCESS_KEY_ID     Credentials AWS
  AWS_SECRET_ACCESS_KEY Credentials AWS
  AWS_SESSION_TOKEN     Credentials AWS (session temporaire)
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

_REPO = Path(__file__).resolve().parents[3]
_SRC = _REPO / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

# Charge le .env à la racine du repo s'il existe (avant tout import backend)
try:
    from dotenv import load_dotenv
    _env = _REPO / ".env"
    if _env.exists():
        load_dotenv(_env)
except ImportError:
    pass

from backend.log.normalization.normalize import normalize  # noqa: E402
from backend.model.bedrock_client import MODEL_ID_DEFAULT  # noqa: E402
from backend.model.incident_llm import (  # noqa: E402
    DEFAULT_ALLOWED_ATTACK_TYPES,
    predict_submission_from_incidents,
)
from backend.model.rules.aggregate_signals import aggregate_signals  # noqa: E402
from backend.model.rules.rules_window import detect_signals_window_1h  # noqa: E402


# ---------------------------------------------------------------------------
# Parsing du fichier de logs
# ---------------------------------------------------------------------------

def _open_file(path: Path):
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8")
    return path.open("r", encoding="utf-8")


def _extract_source(entry: Any) -> dict[str, Any] | None:
    if not isinstance(entry, dict):
        return None
    # Format OpenSearch : {"_source": {...}}
    if "_source" in entry:
        src = entry["_source"]
        return src if isinstance(src, dict) else None
    return entry


def _iter_raw_events(path: Path) -> Iterator[dict[str, Any]]:
    with _open_file(path) as fh:
        content = fh.read().strip()

    # JSON array ?
    if content.startswith("["):
        entries = json.loads(content)
        for e in entries:
            src = _extract_source(e)
            if src is not None:
                yield src
        return

    # NDJSON (une entrée par ligne)
    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        src = _extract_source(entry)
        if src is not None:
            yield src


def load_events(path: Path, *, limit: int | None = None) -> list[dict[str, Any]]:
    events = []
    for i, raw in enumerate(_iter_raw_events(path)):
        if limit is not None and i >= limit:
            break
        events.append(normalize(raw))
    return events


# ---------------------------------------------------------------------------
# Formatage de la sortie
# ---------------------------------------------------------------------------

def _print_section(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def _dump(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)


def _call_llm_with_retry(
    incidents: list[Any],
    *,
    model_id: str,
    region: str,
    max_tokens: int,
    emit,
    max_attempts: int = 6,
    base_delay: float = 10.0,
) -> Any:
    creds: dict[str, str] = {}
    if os.getenv("AWS_ACCESS_KEY_ID"):
        creds["aws_access_key_id"] = os.getenv("AWS_ACCESS_KEY_ID")  # type: ignore[assignment]
    if os.getenv("AWS_SECRET_ACCESS_KEY"):
        creds["aws_secret_access_key"] = os.getenv("AWS_SECRET_ACCESS_KEY")  # type: ignore[assignment]
    if os.getenv("AWS_SESSION_TOKEN"):
        creds["aws_session_token"] = os.getenv("AWS_SESSION_TOKEN")  # type: ignore[assignment]
    for attempt in range(1, max_attempts + 1):
        try:
            return predict_submission_from_incidents(
                incidents,
                allowed_attack_types=DEFAULT_ALLOWED_ATTACK_TYPES,
                region=region,
                model_id=model_id,
                max_tokens=max_tokens,
                inline_aws_credentials=creds or None,
            )
        except Exception as e:
            if "ThrottlingException" not in type(e).__name__ and "ThrottlingException" not in str(e):
                raise
            if attempt == max_attempts:
                raise
            delay = base_delay * (2 ** (attempt - 1))
            emit(f"      Throttling (tentative {attempt}/{max_attempts}) — attente {delay:.0f}s ...")
            time.sleep(delay)


# ---------------------------------------------------------------------------
# Pipeline principale
# ---------------------------------------------------------------------------

def run(
    log_file: Path,
    *,
    limit: int | None,
    skip_llm: bool,
    model_id: str,
    region: str,
    max_tokens: int,
    output_file: Path | None,
) -> None:
    out = open(output_file, "w", encoding="utf-8") if output_file else sys.stdout

    def emit(text: str) -> None:
        print(text, file=out)

    try:
        # 1. Chargement & normalisation
        t0 = time.perf_counter()
        emit(f"[1/4] Chargement de {log_file} ...")
        events = load_events(log_file, limit=limit)
        t1 = time.perf_counter()
        emit(f"      {len(events)} événements normalisés en {t1 - t0:.2f}s")

        if not events:
            emit("Aucun événement chargé — abandon.")
            return

        # 2. Détection des signaux (règles)
        emit(f"\n[2/4] Détection des signaux (fenêtre 1h) ...")
        t2 = time.perf_counter()
        signals = detect_signals_window_1h(events)
        t3 = time.perf_counter()
        emit(f"      {len(signals)} signal(s) détecté(s) en {t3 - t2:.2f}s")

        if signals:
            emit("\n--- Signaux détectés ---")
            for s in signals:
                emit(
                    f"  rule={s.get('rule_id')}  ip={s.get('source_ip')}  "
                    f"user={s.get('username')}  ts={s.get('ts')}"
                )

        # 3. Agrégation des signaux → incidents
        emit(f"\n[3/4] Agrégation des signaux ...")
        incidents = aggregate_signals(signals)
        emit(f"      {len(incidents)} incident(s) agrégé(s)")

        if incidents:
            emit("\n--- Incidents agrégés ---")
            emit(_dump(incidents))

        if skip_llm:
            emit("\n[4/4] (LLM ignoré — mode --no-llm)")
            return

        if not incidents:
            emit("\n[4/4] Aucun incident → pas d'appel LLM.")
            return

        # 4. Prédiction LLM (retry sur ThrottlingException)
        emit(f"\n[4/4] Envoi au LLM ({model_id}, region={region}) ...")
        t4 = time.perf_counter()
        pred = _call_llm_with_retry(
            incidents,
            model_id=model_id,
            region=region,
            max_tokens=max_tokens,
            emit=emit,
        )
        t5 = time.perf_counter()
        emit(f"      Réponse reçue en {t5 - t4:.2f}s")

        emit("\n--- Résultat LLM (brut) ---")
        emit(_dump(pred))

        # Mise en forme ground-truth
        alerts = _to_alerts(pred)
        emit("\n--- Alertes format ground-truth ---")
        emit(_dump(alerts))

    finally:
        if output_file and out is not sys.stdout:
            out.close()
            print(f"\nRésultat écrit dans : {output_file}")


def _to_alerts(pred: Any) -> list[dict[str, Any]]:
    if pred is None:
        return []
    rows = pred if isinstance(pred, list) else [pred]
    out = []
    for row in rows:
        if not isinstance(row, dict) or "detection" not in row:
            continue
        det = row.get("detection") or {}
        attack_type = str(det.get("attack_type") or row.get("challenge_id") or "unknown")
        cid = str(row.get("challenge_id") or attack_type)
        out.append(
            {
                "_index": "ground-truth-ds1",
                "_id": attack_type,
                "_source": {
                    "dataset": 1,
                    "challenge_id": cid,
                    "attack_type": attack_type,
                    "attacker_ips": list(det.get("attacker_ips") or []),
                    "victim_accounts": list(det.get("victim_accounts") or []),
                    "attack_window": {
                        "start": str(det.get("attack_start_time") or "1970-01-01T00:00:00Z"),
                        "end": str(det.get("attack_end_time") or "1970-01-01T00:00:00Z"),
                    },
                    "indicators": dict(det.get("indicators") or {}),
                },
            }
        )
    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Pipeline locale logs raw → normalisation → règles → LLM → alertes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("log_file", type=Path, help="Fichier de logs local (JSON, NDJSON, .gz)")
    p.add_argument(
        "--limit",
        type=int,
        default=None,
        metavar="N",
        help="Nombre max d'événements à charger (défaut : tous)",
    )
    p.add_argument(
        "--no-llm",
        action="store_true",
        help="Arrêter après l'agrégation (pas d'appel Bedrock)",
    )
    p.add_argument(
        "--model-id",
        default=os.getenv("BEDROCK_MODEL_ID", MODEL_ID_DEFAULT),
        help=f"ID du modèle Bedrock (défaut : {MODEL_ID_DEFAULT})",
    )
    p.add_argument(
        "--region",
        default=os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "eu-west-3")),
        help="Région AWS Bedrock (défaut : eu-west-3)",
    )
    p.add_argument(
        "--max-tokens",
        type=int,
        default=int(os.getenv("BEDROCK_MAX_TOKENS", "4096")),
        help="Nombre max de tokens LLM (défaut : 4096)",
    )
    p.add_argument(
        "--output",
        type=Path,
        default=None,
        metavar="FILE",
        help="Fichier de sortie (défaut : stdout)",
    )
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()

    if not args.log_file.exists():
        print(f"Erreur : fichier introuvable : {args.log_file}", file=sys.stderr)
        sys.exit(1)

    run(
        args.log_file,
        limit=args.limit,
        skip_llm=args.no_llm,
        model_id=args.model_id,
        region=args.region,
        max_tokens=args.max_tokens,
        output_file=args.output,
    )
