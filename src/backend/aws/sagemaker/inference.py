"""
Point d’entrée SageMaker sklearn historique (RF + joblib).

Ce dépôt ne fournit plus de code d’inférence pour ce chemin : pour déployer un modèle
sklearn, passe un ``entry_point`` personnalisé à :func:`backend.aws.sagemaker.deploy.deploy_sklearn_endpoint`
(lorsque ce module existe) ou un script équivalent.
"""

from __future__ import annotations


def model_fn(model_dir: str):  # noqa: ARG001
    raise RuntimeError(
        "Aucun chargeur de modèle sklearn n’est défini ici. Fournis un autre entry_point "
        "pour l’endpoint SageMaker."
    )


def input_fn(request_body, request_content_type):  # noqa: ARG001
    raise RuntimeError("Inférence sklearn non configurée — remplacer ce entry_point.")


def predict_fn(data, model):  # noqa: ARG001
    raise RuntimeError("Inférence sklearn non configurée — remplacer ce entry_point.")


def output_fn(prediction, content_type):  # noqa: ARG001
    raise RuntimeError("Inférence sklearn non configurée — remplacer ce entry_point.")


__all__ = ["model_fn", "input_fn", "predict_fn", "output_fn"]
