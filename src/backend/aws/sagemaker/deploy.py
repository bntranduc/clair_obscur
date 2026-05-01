"""Deploy a pre-trained sklearn RF artifact to a SageMaker real-time endpoint."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def default_source_dir() -> Path:
    """Directory that contains the ``backend`` Python package (usually repo ``src``)."""
    return Path(__file__).resolve().parents[3]


def deploy_sklearn_endpoint(
    *,
    model_data: str,
    role: str,
    endpoint_name: str,
    instance_type: str = "ml.m5.large",
    initial_instance_count: int = 1,
    framework_version: str = "1.2-1",
    py_version: str = "py3",
    source_dir: Path | None = None,
    entry_point: str = "backend/aws/sagemaker/inference.py",
    env: dict[str, str] | None = None,
    region: str | None = None,
) -> Any:
    """
    Create an ``SKLearnModel`` and deploy a predictor.

    Requires the ``sagemaker`` Python package and AWS credentials configured.

    ``model_data`` must be an ``s3://`` URI to ``model.tar.gz`` produced by
    :func:`backend.aws.sagemaker.packaging.build_model_tarball`.
    """
    try:
        import boto3
        from sagemaker.deserializers import JSONDeserializer
        from sagemaker.serializers import JSONSerializer
        from sagemaker.session import Session
        from sagemaker.sklearn.model import SKLearnModel
    except ImportError as e:
        raise ImportError(
            "Install the SageMaker SDK: pip install 'sagemaker>=2.190,<3'"
        ) from e

    src = Path(source_dir) if source_dir is not None else default_source_dir()
    if not (src / "backend").is_dir():
        raise FileNotFoundError(f"source_dir must contain backend/ package: {src}")

    boto_sess = boto3.Session(region_name=region)
    sm_sess = Session(boto_session=boto_sess)

    model = SKLearnModel(
        model_data=model_data,
        role=role,
        entry_point=entry_point,
        framework_version=framework_version,
        py_version=py_version,
        source_dir=str(src),
        env=env or {},
        sagemaker_session=sm_sess,
    )

    predictor = model.deploy(
        initial_instance_count=initial_instance_count,
        instance_type=instance_type,
        endpoint_name=endpoint_name,
        serializer=JSONSerializer(),
        deserializer=JSONDeserializer(),
    )
    return predictor
