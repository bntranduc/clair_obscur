"""
SageMaker serving entry point for the attack RF.

Delegates to ``backend.model.attack_predictor.inference`` so ``source_dir`` can be
the repo ``src`` tree (imports ``backend.*``).
"""

from __future__ import annotations

from backend.model.attack_predictor.inference import (  # noqa: F401
    input_fn,
    model_fn,
    output_fn,
    predict_fn,
)

__all__ = ["model_fn", "input_fn", "predict_fn", "output_fn"]
