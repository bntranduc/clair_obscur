"""
Train a RandomForest on labeled ``NormalizedEvent`` rows for SageMaker or local runs.

SageMaker sklearn estimator (script mode) sets ``SM_MODEL_DIR`` and ``SM_CHANNEL_TRAINING``.
Put ``train.jsonl`` in the training channel; optionally ``ground_truth_ds1.json`` in the same
folder (or pass ``--ground-truth-file``).

Each JSONL line:
  {"attack_type": "ssrf", "event": { ... NormalizedEvent fields ... }}

CLI example (local) — sans ``--model-dir``, les artefacts vont dans ``predictors/`` :

  PYTHONPATH=src python -m backend.model.attack_predictor.train \\
    --train-data datasets/sample_attack_train.jsonl \\
    --ground-truth datasets/ground_truth_ds1.json

SageMaker définit ``SM_MODEL_DIR`` ; en local le défaut est
``backend/model/attack_predictor/predictors/``.

Ensuite packaging / upload SageMaker (même répertoire ``model-dir``) :

  PYTHONPATH=src python -m backend.aws.sagemaker.cli package-upload \\
    --model-dir src/backend/model/attack_predictor/predictors -o /tmp/model.tar.gz \\
    --bucket BUCKET --key PREFIX/model.tar.gz
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Iterator

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

from features import event_to_feature_vector, feature_names
from labels import (
    load_attack_types_from_ground_truth,
    validate_labels_against_ground_truth,
)
from paths import DEFAULT_LOCAL_MODEL_DIR

_ARTIFACT_MODEL = "model.joblib"
_ARTIFACT_ENCODER = "label_encoder.joblib"
_ARTIFACT_META = "metadata.json"


def _iter_labeled_events(path: Path) -> Iterator[tuple[dict[str, Any], str]]:
    with path.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"{path}:{line_no}: object expected")
            label = row.get("attack_type") or row.get("label")
            ev = row.get("event") or row.get("normalized_event")
            if not isinstance(label, str) or not label.strip():
                raise ValueError(f"{path}:{line_no}: missing attack_type")
            if not isinstance(ev, dict):
                raise ValueError(f"{path}:{line_no}: missing event object")
            yield ev, label.strip()


def _load_training_arrays(
    train_file: Path,
    *,
    ground_truth_path: Path,
) -> tuple[np.ndarray, np.ndarray]:
    labels_seen: set[str] = set()
    xs: list[np.ndarray] = []
    ys: list[str] = []
    for ev, lab in _iter_labeled_events(train_file):
        labels_seen.add(lab)
        xs.append(event_to_feature_vector(ev))
        ys.append(lab)
    if not xs:
        raise ValueError(f"No training rows in {train_file}")
    validate_labels_against_ground_truth(labels_seen, ground_truth_path)
    x = np.stack(xs, axis=0)
    y = np.asarray(ys)
    return x, y


def train_and_save(
    *,
    train_path: Path,
    ground_truth_path: Path,
    model_dir: Path,
    n_estimators: int,
    max_depth: int | None,
    min_samples_leaf: int,
    random_state: int,
    test_size: float,
) -> dict[str, Any]:
    allowed = load_attack_types_from_ground_truth(ground_truth_path)
    x, y = _load_training_arrays(train_path, ground_truth_path=ground_truth_path)

    enc = LabelEncoder()
    enc.fit(allowed)

    y_enc = enc.transform(y)

    if test_size > 0 and len(y) >= 5:
        x_tr, x_va, y_tr, y_va = train_test_split(
            x, y_enc, test_size=test_size, random_state=random_state, stratify=y_enc
        )
    else:
        x_tr, y_tr = x, y_enc
        x_va = y_va = None

    clf = RandomForestClassifier(
        n_estimators=n_estimators,
        max_depth=max_depth,
        min_samples_leaf=min_samples_leaf,
        random_state=random_state,
        class_weight="balanced_subsample",
        n_jobs=-1,
    )
    clf.fit(x_tr, y_tr)

    metrics: dict[str, Any] = {"allowed_classes": allowed}
    if x_va is not None and len(x_va) > 0:
        y_hat = clf.predict(x_va)
        report = classification_report(
            y_va,
            y_hat,
            labels=list(range(len(enc.classes_))),
            target_names=list(enc.classes_),
            zero_division=0,
            output_dict=True,
        )
        metrics["validation_report"] = report

    model_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(clf, model_dir / _ARTIFACT_MODEL)
    joblib.dump(enc, model_dir / _ARTIFACT_ENCODER)

    meta = {
        "classes": [str(c) for c in enc.classes_.tolist()],
        "feature_names": feature_names(),
        "feature_dim": int(x.shape[1]),
        "ground_truth_source": str(ground_truth_path),
        "train_rows": int(x.shape[0]),
        "hyperparameters": {
            "n_estimators": n_estimators,
            "max_depth": max_depth,
            "min_samples_leaf": min_samples_leaf,
            "random_state": random_state,
            "test_size": test_size,
        },
    }
    (model_dir / _ARTIFACT_META).write_text(json.dumps(meta, indent=2), encoding="utf-8")

    metrics_path = model_dir / "metrics.json"
    metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    return metrics


def _resolve_train_file(train_dir: Path, explicit: str | None) -> Path:
    if explicit:
        p = train_dir / explicit if not Path(explicit).is_absolute() else Path(explicit)
        if p.is_file():
            return p
        raise FileNotFoundError(f"Train file not found: {p}")
    for name in ("train.jsonl", "training.jsonl", "labeled_events.jsonl"):
        p = train_dir / name
        if p.is_file():
            return p
    raise FileNotFoundError(
        f"No train.jsonl under {train_dir}; pass --train-data path explicitly."
    )


def _resolve_ground_truth(train_dir: Path, explicit: str | None) -> Path:
    if explicit:
        p = Path(explicit)
        if not p.is_absolute():
            cand = train_dir / explicit
            p = cand if cand.is_file() else Path(explicit)
        if p.is_file():
            return p
        raise FileNotFoundError(f"Ground truth file not found: {p}")
    for name in ("ground_truth_ds1.json", "ground_truth.json"):
        p = train_dir / name
        if p.is_file():
            return p
    raise FileNotFoundError(
        "Ground truth JSON not found in training channel; "
        "upload ground_truth_ds1.json alongside train.jsonl or pass --ground-truth."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Train RandomForest attack-type classifier")
    default_model_dir = os.getenv("SM_MODEL_DIR", str(DEFAULT_LOCAL_MODEL_DIR.resolve()))
    default_train_dir = os.getenv("SM_CHANNEL_TRAINING", ".")
    parser.add_argument("--model-dir", type=str, default=default_model_dir)
    parser.add_argument("--train-channel", type=str, default=default_train_dir, help="SageMaker training channel root")
    parser.add_argument("--train-data", type=str, default=None, help="Filename inside channel or absolute path")
    parser.add_argument("--ground-truth", type=str, default=os.getenv("GROUND_TRUTH_PATH", ""))
    parser.add_argument("--ground-truth-file", type=str, default=None, help="Inside train channel if relative")
    parser.add_argument("--n-estimators", type=int, default=200)
    parser.add_argument("--max-depth", type=int, default=None)
    parser.add_argument("--min-samples-leaf", type=int, default=1)
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--test-size", type=float, default=0.2)

    args = parser.parse_args()
    train_root = Path(args.train_channel)
    train_file = _resolve_train_file(train_root, args.train_data)

    if args.ground_truth and str(args.ground_truth).strip():
        gt_path = Path(args.ground_truth)
    elif args.ground_truth_file:
        gt_path = _resolve_ground_truth(train_root, args.ground_truth_file)
    else:
        gt_path = _resolve_ground_truth(train_root, None)

    metrics = train_and_save(
        train_path=train_file,
        ground_truth_path=gt_path,
        model_dir=Path(args.model_dir),
        n_estimators=args.n_estimators,
        max_depth=args.max_depth if args.max_depth is not None else None,
        min_samples_leaf=args.min_samples_leaf,
        random_state=args.random_state,
        test_size=args.test_size,
    )
    print(json.dumps({"status": "ok", "metrics_keys": list(metrics.keys())}))


if __name__ == "__main__":
    main()
