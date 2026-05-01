"""Empaqueter des artefacts sklearn (``model.joblib``, etc.) en ``model.tar.gz`` pour SageMaker."""

from __future__ import annotations

import tarfile
from pathlib import Path

_REQUIRED = ("model.joblib", "label_encoder.joblib", "metadata.json")


def assert_model_dir_ready(model_dir: Path) -> None:
    missing = [name for name in _REQUIRED if not (model_dir / name).is_file()]
    if missing:
        raise FileNotFoundError(
            f"Model directory {model_dir} missing files: {', '.join(missing)}. "
            f"Expected sklearn artefacts at root: {', '.join(_REQUIRED)}."
        )


def build_model_tarball(model_dir: Path, output_tar_gz: Path) -> Path:
    """Write ``model.tar.gz`` with artefacts at the **root** of the archive (sklearn hosting convention)."""
    model_dir = model_dir.resolve()
    assert_model_dir_ready(model_dir)
    output_tar_gz = output_tar_gz.resolve()
    output_tar_gz.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(output_tar_gz, "w:gz") as tar:
        for name in _REQUIRED:
            tar.add(model_dir / name, arcname=name)
    return output_tar_gz
