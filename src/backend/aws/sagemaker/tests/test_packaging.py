from __future__ import annotations

import tarfile
from pathlib import Path

import pytest

from backend.aws.sagemaker.packaging import assert_model_dir_ready, build_model_tarball


def test_assert_model_dir_ready_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        assert_model_dir_ready(tmp_path)


def test_build_model_tarball_roundtrip(tmp_path: Path) -> None:
    mdir = tmp_path / "model"
    mdir.mkdir()
    for name in ("model.joblib", "label_encoder.joblib", "metadata.json"):
        (mdir / name).write_bytes(b"x")
    out = tmp_path / "model.tar.gz"
    build_model_tarball(mdir, out)
    assert out.is_file()
    with tarfile.open(out, "r:gz") as tar:
        names = tar.getnames()
    assert set(names) == {"model.joblib", "label_encoder.joblib", "metadata.json"}
