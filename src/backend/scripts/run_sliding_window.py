#!/usr/bin/env python3
"""
Pipeline locale sur fenêtre glissante de fichiers JSONL.

Chaque fichier du dossier couvre ~5 minutes de logs. Le script concatène les
événements de W fichiers consécutifs (fenêtre) et fait avancer la fenêtre de S
fichiers à chaque itération (pas).

Usage :
  python run_sliding_window.py [options]

Exemples :
  # Fenêtre 1h (12 fichiers × 5 min), pas de 1 fichier, backend API
  python run_sliding_window.py --backend api

  # Fenêtre de 6 fichiers (~30 min), pas de 6 (fenêtres disjointes)
  python run_sliding_window.py --window 6 --step 6 --no-llm

  # Dossier custom, sortie JSON
  python run_sliding_window.py --input datasets/finale/ingestion --output results.json

Variables d'environnement :
  MODEL_BACKEND         'api' ou 'bedrock' (défaut : bedrock)
  ANTHROPIC_API_KEY     Clé API Anthropic (backend=api)
  ANTHROPIC_MODEL_ID    Modèle Anthropic direct (défaut : claude-opus-4-6)
  BEDROCK_MODEL_ID      ID du modèle Bedrock
  AWS_REGION            Région AWS (défaut : eu-west-3)
  AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_SESSION_TOKEN
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Iterator

_REPO = Path(__file__).resolve().parents[3]
_SRC = _REPO / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

try:
    from dotenv import load_dotenv
    _env = _REPO / ".env"
    if _env.exists():
        load_dotenv(_env)
except ImportError:
    pass

from backend.log.normalization.normalize import normalize  # noqa: E402
from backend.model.api_client import API_MODEL_ID_DEFAULT  # noqa: E402
from backend.model.bedrock_client import MODEL_ID_DEFAULT  # noqa: E402
from backend.model.incident_llm import (  # noqa: E402
    DEFAULT_ALLOWED_ATTACK_TYPES,
    predict_submission_from_incidents,
)
from backend.model.rules.aggregate_signals import aggregate_signals  # noqa: E402
from backend.model.rules.rules_window import detect_signals_window_1h  # noqa: E402

DEFAULT_INPUT = _REPO / "datasets/finale/ingestion"
DEFAULT_WINDOW = 12   # ~1h à 5 min/fichier
DEFAULT_STEP = 1


# ---------------------------------------------------------------------------
# Chargement
# ---------------------------------------------------------------------------

def _iter_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            yield rec.get("_source", rec) if isinstance(rec, dict) else rec


def load_files(files: list[Path]) -> list[Any]:
    events = []
    for f in files:
        for i, raw in enumerate(_iter_jsonl(f)):
            events.append(normalize(raw, {"file": f.name, "line": i}))
    return events


# ---------------------------------------------------------------------------
# LLM avec retry throttling
# ---------------------------------------------------------------------------

def _call_llm(
    incidents: list[Any],
    *,
    backend: str,
    model_id: str,
    region: str,
    max_tokens: int,
    api_key: str | None,
    api_model_id: str,
    emit,
    max_attempts: int = 6,
    base_delay: float = 10.0,
) -> Any:
    creds: dict[str, str] = {}
    if backend == "bedrock":
        for env_key, cred_key in [
            ("AWS_ACCESS_KEY_ID", "aws_access_key_id"),
            ("AWS_SECRET_ACCESS_KEY", "aws_secret_access_key"),
            ("AWS_SESSION_TOKEN", "aws_session_token"),
        ]:
            val = os.getenv(env_key)
            if val:
                creds[cred_key] = val

    for attempt in range(1, max_attempts + 1):
        try:
            return predict_submission_from_incidents(
                incidents,
                backend=backend,  # type: ignore[arg-type]
                allowed_attack_types=DEFAULT_ALLOWED_ATTACK_TYPES,
                region=region,
                model_id=model_id,
                max_tokens=max_tokens,
                inline_aws_credentials=creds or None,
                api_key=api_key,
                api_model_id=api_model_id,
            )
        except Exception as e:
            if "ThrottlingException" not in type(e).__name__ and "ThrottlingException" not in str(e):
                raise
            if attempt == max_attempts:
                raise
            delay = base_delay * (2 ** (attempt - 1))
            emit(f"    Throttling ({attempt}/{max_attempts}) — attente {delay:.0f}s ...")
            time.sleep(delay)


# ---------------------------------------------------------------------------
# Pipeline sur une fenêtre
# ---------------------------------------------------------------------------

def run_window(
    files: list[Path],
    window_idx: int,
    *,
    backend: str,
    model_id: str,
    region: str,
    max_tokens: int,
    api_key: str | None,
    api_model_id: str,
    skip_llm: bool,
    emit,
) -> dict[str, Any]:
    names = [f.name for f in files]
    emit(f"\n{'─' * 64}")
    emit(f"Fenêtre {window_idx}  ({len(files)} fichiers : {names[0]} … {names[-1]})")
    emit(f"{'─' * 64}")

    t0 = time.perf_counter()
    events = load_files(files)
    emit(f"  [1/3] {len(events):,} événements normalisés en {time.perf_counter() - t0:.2f}s")

    signals = detect_signals_window_1h(events)
    emit(f"  [2/3] {len(signals)} signal(s) détecté(s)")
    for s in signals:
        emit(f"        rule={s.get('rule_id')}  ip={s.get('source_ip')}  user={s.get('username')}")

    incidents = aggregate_signals(signals)
    emit(f"        {len(incidents)} incident(s) agrégé(s)")

    result: dict[str, Any] = {
        "window": window_idx,
        "files": names,
        "events": len(events),
        "signals": len(signals),
        "incidents": len(incidents),
        "alerts": [],
        "error": None,
    }

    if skip_llm or not incidents:
        if not skip_llm and not incidents:
            emit("  [3/3] Aucun incident — pas d'appel LLM.")
        return result

    llm_label = f"api/{api_model_id}" if backend == "api" else f"bedrock/{model_id}"
    emit(f"  [3/3] LLM ({llm_label}) ...")
    t_llm = time.perf_counter()
    try:
        pred = _call_llm(
            incidents,
            backend=backend,
            model_id=model_id,
            region=region,
            max_tokens=max_tokens,
            api_key=api_key,
            api_model_id=api_model_id,
            emit=emit,
        )
        elapsed = time.perf_counter() - t_llm
        alerts = pred if isinstance(pred, list) else ([pred] if isinstance(pred, dict) else [])
        emit(f"        {len(alerts)} alerte(s) en {elapsed:.2f}s")
        for a in alerts:
            emit(f"        → {a.get('challenge_id')} | sév={a.get('severity')}")
        result["alerts"] = alerts
    except Exception as e:
        emit(f"        ERREUR LLM : {e}")
        result["error"] = str(e)

    return result


# ---------------------------------------------------------------------------
# Boucle principale
# ---------------------------------------------------------------------------

def run(
    input_dir: Path,
    *,
    window: int,
    step: int,
    backend: str,
    model_id: str,
    region: str,
    max_tokens: int,
    api_key: str | None,
    api_model_id: str,
    skip_llm: bool,
    output_dir: Path | None,
    start_at: int,
) -> None:
    files = sorted(f for f in input_dir.glob("*.jsonl") if not any(c in f.suffix for c in ["~", "."]) or f.suffix == ".jsonl")
    if not files:
        print(f"Aucun fichier .jsonl dans {input_dir}", file=sys.stderr)
        sys.exit(1)

    total_windows = max(0, (len(files) - window) // step + 1)

    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)

    def emit(text: str, out=None) -> None:
        print(text, file=out or sys.stdout)

    emit(f"Dossier   : {input_dir}")
    emit(f"Fichiers  : {len(files)}  ({files[0].name} … {files[-1].name})")
    emit(f"Fenêtre   : {window} fichiers  |  Pas : {step} fichier(s)")
    emit(f"Fenêtres  : {total_windows}  (début à l'index {start_at})")
    if output_dir:
        emit(f"Sortie    : {output_dir}/window_NNNN.{{log,json}}")

    all_results = []
    t_total = time.perf_counter()

    for i in range(start_at, len(files) - window + 1, step):
        window_files = files[i : i + window]
        window_idx = (i - start_at) // step

        # Fichiers de sortie par fenêtre
        if output_dir:
            win_dir = output_dir / f"window_{window_idx:04d}"
            win_dir.mkdir(parents=True, exist_ok=True)
            log_path = win_dir / "run.log"
            json_path = win_dir / "result.json"
            log_out = open(log_path, "w", encoding="utf-8")
        else:
            log_out = None

        def _emit(text: str, _out=log_out) -> None:
            print(text, file=_out or sys.stdout)
            if _out is not None:
                print(text)  # echo stdout aussi

        try:
            result = run_window(
                window_files,
                window_idx,
                backend=backend,
                model_id=model_id,
                region=region,
                max_tokens=max_tokens,
                api_key=api_key,
                api_model_id=api_model_id,
                skip_llm=skip_llm,
                emit=_emit,
            )
        finally:
            if log_out:
                log_out.close()

        if output_dir:
            json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

        all_results.append(result)

    emit(f"\n{'=' * 64}")
    emit(f"Terminé : {len(all_results)} fenêtre(s) en {time.perf_counter() - t_total:.1f}s")
    total_alerts = sum(len(r["alerts"]) for r in all_results)
    emit(f"Total alertes : {total_alerts}")

    if output_dir:
        summary_path = output_dir / "summary.json"
        summary_path.write_text(json.dumps(all_results, ensure_ascii=False, indent=2), encoding="utf-8")
        emit(f"Résumé global : {summary_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Pipeline locale sur fenêtre glissante de fichiers JSONL",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help=f"Dossier contenant les fichiers JSONL (défaut : {DEFAULT_INPUT})",
    )
    p.add_argument(
        "--window",
        type=int,
        default=DEFAULT_WINDOW,
        metavar="N",
        help=f"Nombre de fichiers par fenêtre (défaut : {DEFAULT_WINDOW} ≈ 1h)",
    )
    p.add_argument(
        "--step",
        type=int,
        default=DEFAULT_STEP,
        metavar="N",
        help=f"Pas de glissement en fichiers (défaut : {DEFAULT_STEP})",
    )
    p.add_argument(
        "--start-at",
        type=int,
        default=0,
        metavar="N",
        help="Indice du premier fichier à traiter (défaut : 0)",
    )
    p.add_argument(
        "--no-llm",
        action="store_true",
        help="Arrêter après l'agrégation (pas d'appel LLM)",
    )
    p.add_argument(
        "--backend",
        default=os.getenv("MODEL_BACKEND", "bedrock"),
        choices=["bedrock", "api"],
        help="Backend LLM : 'bedrock' (défaut) ou 'api' (Anthropic API directe)",
    )
    # Bedrock
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
    # API directe
    p.add_argument(
        "--api-key",
        default=os.getenv("ANTHROPIC_API_KEY"),
        help="Clé API Anthropic (backend=api ; défaut : $ANTHROPIC_API_KEY)",
    )
    p.add_argument(
        "--api-model-id",
        default=os.getenv("ANTHROPIC_MODEL_ID", API_MODEL_ID_DEFAULT),
        help=f"Modèle Anthropic direct (défaut : {API_MODEL_ID_DEFAULT})",
    )
    p.add_argument(
        "--max-tokens",
        type=int,
        default=int(os.getenv("BEDROCK_MAX_TOKENS", "4096")),
        help="Nombre max de tokens LLM (défaut : 4096)",
    )
    p.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        metavar="DIR",
        help="Dossier de sortie : window_NNNN.log + window_NNNN.json par fenêtre, summary.json global",
    )
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()

    if not args.input.is_dir():
        print(f"Erreur : dossier introuvable : {args.input}", file=sys.stderr)
        sys.exit(1)
    if args.window < 1:
        print("--window doit être >= 1", file=sys.stderr)
        sys.exit(1)
    if args.step < 1:
        print("--step doit être >= 1", file=sys.stderr)
        sys.exit(1)

    run(
        args.input,
        window=args.window,
        step=args.step,
        backend=args.backend,
        model_id=args.model_id,
        region=args.region,
        max_tokens=args.max_tokens,
        api_key=args.api_key,
        api_model_id=args.api_model_id,
        skip_llm=args.no_llm,
        output_dir=args.output_dir,
        start_at=args.start_at,
    )
