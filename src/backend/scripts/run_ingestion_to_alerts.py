#!/usr/bin/env python3
"""
Pipeline ingestion → alertes : lit tous les fichiers JSONL d'un répertoire,
détecte les signaux, agrège, appelle le LLM et écrit database/alerts.json.

Usage :
  python run_ingestion_to_alerts.py [--ingestion-dir DIR] [--output FILE]

Variables d'environnement :
  LOCAL_LOGS_DIR        Répertoire d'ingestion (priorité sur --ingestion-dir)
  BEDROCK_MODEL_ID      Modèle Bedrock (défaut : predict.MODEL_ID_DEFAULT)
  AWS_REGION            Région Bedrock (défaut : eu-west-3)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[3]
_SRC = _REPO / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

try:
    from dotenv import load_dotenv
    _env = _REPO / ".env"
    if _env.exists():
        load_dotenv(_env)
except ImportError:
    pass

from backend.log.normalization.normalize import normalize  # noqa: E402
from backend.model.rules.aggregate_signals import aggregate_signals  # noqa: E402
from backend.model.rules.rules_window import detect_signals_window_1h  # noqa: E402
from backend.model.predict import (  # noqa: E402
    DEFAULT_DETECTION_TIME_SECONDS,
    MODEL_ID_DEFAULT,
    predict_from_incidents,
)
from backend.alerts.store import alerts_json_path  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _iter_events(jsonl_path: Path):
    with jsonl_path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, dict):
                continue
            src = row["_source"] if "_source" in row else row
            if isinstance(src, dict):
                yield normalize(src)


def _collect_signals(ingestion_dir: Path) -> list[dict[str, Any]]:
    files = sorted(ingestion_dir.glob("*.jsonl"))
    total_files = len(files)
    all_signals: list[dict[str, Any]] = []

    for i, path in enumerate(files, 1):
        print(f"  [{i}/{total_files}] {path.name} ...", end=" ", flush=True)
        t0 = time.perf_counter()
        events = list(_iter_events(path))
        signals = detect_signals_window_1h(events)
        all_signals.extend(signals)
        print(f"{len(events)} events → {len(signals)} signaux ({time.perf_counter()-t0:.1f}s)")

    return all_signals


def _to_alert_record(pred: dict[str, Any], numeric_id: int) -> dict[str, Any]:
    det = pred.get("detection") or {}
    attack_type = str(det.get("attack_type") or pred.get("challenge_id") or "unknown")
    record = {
        "id": f"pred-{attack_type}",
        "numeric_id": numeric_id,
        **pred,
    }
    if "challenge_id" not in record:
        record["challenge_id"] = attack_type
    if "detection_time_seconds" not in record:
        record["detection_time_seconds"] = DEFAULT_DETECTION_TIME_SECONDS
    return record


def _call_llm(incidents: list[Any], *, model_id: str, region: str) -> list[dict[str, Any]]:
    creds: dict[str, str] = {}
    for k in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
        v = os.getenv(k)
        if v:
            creds[k.lower()] = v

    try:
        return predict_from_incidents(
            incidents,
            region=region,
            model_id=model_id,
            inline_aws_credentials=creds or None,
        )
    except Exception as exc:
        raise RuntimeError("LLM prediction failed") from exc


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ingestion-dir", type=Path, default=None,
                        help="Répertoire des fichiers JSONL (défaut : LOCAL_LOGS_DIR ou datasets/finale/ingestion)")
    parser.add_argument("--output", type=Path, default=None,
                        help="Fichier de sortie (défaut : database/alerts.json)")
    args = parser.parse_args()

    ingestion_dir = (
        args.ingestion_dir
        or Path((os.getenv("LOCAL_LOGS_DIR") or "").strip() or (_REPO / "datasets" / "finale" / "ingestion"))
    )
    output_path = args.output or alerts_json_path()

    if not ingestion_dir.is_dir():
        sys.exit(f"Répertoire introuvable : {ingestion_dir}")

    print(f"Ingestion dir : {ingestion_dir}")
    print(f"Output        : {output_path}")
    print()

    # 1. Détection des signaux sur tous les fichiers
    print("[1/3] Détection des signaux ...")
    t0 = time.perf_counter()
    all_signals = _collect_signals(ingestion_dir)
    print(f"      Total : {len(all_signals)} signaux en {time.perf_counter()-t0:.1f}s\n")

    # 2. Agrégation
    print("[2/3] Agrégation ...")
    incidents = aggregate_signals(all_signals)
    print(f"      {len(incidents)} incident(s) agrégé(s)\n")

    model_id = (os.getenv("BEDROCK_MODEL_ID") or MODEL_ID_DEFAULT).strip()
    region = (os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "eu-west-3").strip()

    print(f"[3/3] Appel Bedrock ({model_id}) ...")
    t3 = time.perf_counter()
    raw_preds = _call_llm(incidents, model_id=model_id, region=region)
    print(f"      {len(raw_preds)} prédiction(s) reçues en {time.perf_counter()-t3:.1f}s")
    alerts = [_to_alert_record(p, i + 1) for i, p in enumerate(raw_preds)]

    # Écriture
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"alerts": alerts, "count": len(alerts)}
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n{len(alerts)} alerte(s) écrites dans {output_path}")


if __name__ == "__main__":
    main()
