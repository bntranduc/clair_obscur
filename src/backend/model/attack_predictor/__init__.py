"""
RandomForest attack-type classifier aligned with ``datasets/ground_truth_ds1.json`` labels.

- ``features``: map ``NormalizedEvent`` → numeric vector
- ``train``: SageMaker-compatible training entrypoint
- ``inference``: SageMaker ``model_fn`` / ``input_fn`` / ``predict_fn`` / ``output_fn``
- ``AttackPredictor``: load artifacts from ``model_dir`` (local or endpoint)

Deploy on SageMaker (sklearn container): point ``entry_point`` at ``train.py`` for fitting,
package ``backend`` so imports resolve, or vendor a flat copy for the container image.

At inference, set ``SAGEMAKER_PROGRAM`` / model execution to load ``inference.py`` per AWS docs
for the sklearn inference toolkit.
"""

from backend.model.attack_predictor.features import (
    FEATURE_DIM,
    event_to_feature_vector,
    feature_names,
)
from backend.model.attack_predictor.labels import load_attack_types_from_ground_truth
from backend.model.attack_predictor.paths import DEFAULT_LOCAL_MODEL_DIR
from backend.model.attack_predictor.predictor import AttackPredictor

__all__ = [
    "AttackPredictor",
    "DEFAULT_LOCAL_MODEL_DIR",
    "FEATURE_DIM",
    "event_to_feature_vector",
    "feature_names",
    "load_attack_types_from_ground_truth",
]
