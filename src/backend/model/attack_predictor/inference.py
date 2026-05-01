"""
SageMaker sklearn container hooks for ``AttackPredictor``.

Expected ``Content-Type``: ``application/json``.
Body shapes:

- Single event: ``{"event": { ... NormalizedEvent ... }}``
- Batch: ``{"instances": [ {"event": {...}}, ... ] }``

Response JSON includes ``predictions`` list with ``predicted_attack_type`` and ``probabilities``.
"""

from __future__ import annotations
import json
from typing import Any
import numpy as np
from features import event_to_feature_vector
from predictor import AttackPredictor

_predictor: AttackPredictor | None = None


def model_fn(model_dir: str) -> AttackPredictor:
    global _predictor
    _predictor = AttackPredictor.load(model_dir)
    return _predictor


def input_fn(request_body: bytes, request_content_type: str) -> Any:
    if request_content_type and "json" not in request_content_type.lower():
        raise ValueError(f"Unsupported content type: {request_content_type}")
    payload = json.loads(request_body.decode("utf-8"))
    return payload


def predict_fn(payload: Any, model: AttackPredictor) -> dict[str, Any]:
    if isinstance(payload, dict) and "instances" in payload:
        instances = payload["instances"]
        if not isinstance(instances, list):
            raise ValueError("instances must be a list")
        events = []
        for i, row in enumerate(instances):
            if not isinstance(row, dict):
                raise ValueError(f"instances[{i}] must be an object")
            ev = row.get("event") or row.get("normalized_event") or row
            if not isinstance(ev, dict):
                raise ValueError(f"instances[{i}] missing event")
            events.append(ev)
        mat = np.stack([event_to_feature_vector(e) for e in events], axis=0)
        out: list[dict[str, Any]] = []
        for i in range(mat.shape[0]):
            pred = model.predict_proba_vector(mat[i])
            label, probs, _ = pred
            out.append({"predicted_attack_type": label, "probabilities": probs})
        return {"predictions": out}

    if isinstance(payload, dict):
        ev = payload.get("event") or payload.get("normalized_event") or payload
        if not isinstance(ev, dict):
            raise ValueError("Expected JSON object with event/normalized_event")
        result = model.predict_event(ev)
        return {"predictions": [result]}

    raise ValueError("Unsupported JSON payload")


def output_fn(prediction: Any, response_content_type: str) -> bytes:
    if response_content_type and "json" not in response_content_type.lower():
        raise ValueError(f"Unsupported response type: {response_content_type}")
    return json.dumps(prediction, ensure_ascii=False).encode("utf-8")
