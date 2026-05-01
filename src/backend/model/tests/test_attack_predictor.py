from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from backend.model.attack_predictor.features import FEATURE_DIM, event_to_feature_vector, feature_names
from backend.model.attack_predictor.labels import load_attack_types_from_ground_truth
from backend.model.attack_predictor.predictor import AttackPredictor
from backend.model.attack_predictor.train import train_and_save


_REPO_ROOT = Path(__file__).resolve().parents[4]
_GROUND_TRUTH = _REPO_ROOT / "datasets" / "ground_truth_ds1.json"
_SAMPLE_TRAIN = _REPO_ROOT / "datasets" / "sample_attack_train.jsonl"


def test_feature_dim_matches_names() -> None:
    assert len(feature_names()) == FEATURE_DIM
    v = event_to_feature_vector({})
    assert v.shape == (FEATURE_DIM,)


def test_load_attack_types_from_ground_truth_file() -> None:
    types = load_attack_types_from_ground_truth(_GROUND_TRUTH)
    assert "ssrf" in types
    assert "credential_stuffing" in types
    assert len(types) >= 5


@pytest.mark.skipif(not _GROUND_TRUTH.is_file(), reason="ground_truth_ds1.json missing")
@pytest.mark.skipif(not _SAMPLE_TRAIN.is_file(), reason="sample_attack_train.jsonl missing")
def test_train_and_predict_roundtrip(tmp_path: Path) -> None:
    model_dir = tmp_path / "model"
    train_and_save(
        train_path=_SAMPLE_TRAIN,
        ground_truth_path=_GROUND_TRUTH,
        model_dir=model_dir,
        n_estimators=50,
        max_depth=8,
        min_samples_leaf=1,
        random_state=0,
        test_size=0.0,
    )
    clf = AttackPredictor.load(model_dir)
    assert len(clf.classes) >= 5
    row = json.loads(_SAMPLE_TRAIN.read_text(encoding="utf-8").splitlines()[0])
    ev = row["event"]
    out = clf.predict_event(ev)
    assert out["predicted_attack_type"] in clf.classes
    assert abs(sum(out["probabilities"].values()) - 1.0) < 1e-5


def test_predict_proba_columns_align_with_strings() -> None:
    ev = {"log_source": "network", "bytes_sent": 100.0}
    v = event_to_feature_vector(ev)
    assert v.dtype == np.float32
    assert not np.isnan(v).any()
