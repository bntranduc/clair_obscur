from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder

from backend.model.attack_predictor.features import event_to_feature_vector

_ARTIFACT_MODEL = "model.joblib"
_ARTIFACT_ENCODER = "label_encoder.joblib"
_ARTIFACT_META = "metadata.json"


class AttackPredictor:
    """Loads SageMaker training artifacts and scores ``NormalizedEvent``-like dicts."""

    def __init__(
        self,
        model: RandomForestClassifier,
        label_encoder: LabelEncoder,
        *,
        meta: Mapping[str, Any] | None = None,
    ) -> None:
        self._model = model
        self._label_encoder = label_encoder
        self._meta = dict(meta or {})

    @classmethod
    def load(cls, model_dir: str | Path) -> AttackPredictor:
        root = Path(model_dir)
        model = joblib.load(root / _ARTIFACT_MODEL)
        enc = joblib.load(root / _ARTIFACT_ENCODER)
        if not isinstance(enc, LabelEncoder):
            raise TypeError("label_encoder.joblib must contain a sklearn LabelEncoder")
        meta_path = root / _ARTIFACT_META
        meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.is_file() else {}
        return cls(model, enc, meta=meta)

    @property
    def classes(self) -> list[str]:
        order = np.asarray(self._model.classes_, dtype=int)
        labels = self._label_encoder.inverse_transform(order)
        return [str(x) for x in labels]

    def predict_proba_vector(self, x: np.ndarray) -> tuple[str, dict[str, float], np.ndarray]:
        if x.ndim == 1:
            x = x.reshape(1, -1)
        proba = self._model.predict_proba(x)[0]
        order = np.asarray(self._model.classes_, dtype=int)
        label_names = [str(l) for l in self._label_encoder.inverse_transform(order)]
        scores = {label_names[i]: float(proba[i]) for i in range(len(label_names))}
        k = int(np.argmax(proba))
        label = label_names[k]
        return label, scores, proba

    def predict_event(self, event: Mapping[str, Any]) -> dict[str, Any]:
        vec = event_to_feature_vector(event)
        label, scores, proba = self.predict_proba_vector(vec)
        return {
            "predicted_attack_type": label,
            "probabilities": scores,
            "top_probability": float(np.max(proba)),
            "feature_dim": int(vec.shape[0]),
        }
