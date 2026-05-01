"""
AWS SageMaker utilities for the attack RandomForest (local train → ``model.tar.gz`` → S3 → endpoint).

Typical flow::

  # 1) Train locally (default ``model-dir``: backend/model/attack_predictor/predictors/)
  PYTHONPATH=src python -m backend.model.attack_predictor.train ...

  # 2) Package + upload
  PYTHONPATH=src python -m backend.aws.sagemaker.cli package-upload \\
    --model-dir src/backend/model/attack_predictor/predictors -o /tmp/model.tar.gz \\
    --bucket MY_BUCKET --key sagemaker/attack-rf/model.tar.gz

  # 3) Deploy (needs ``pip install 'sagemaker>=2.190,<3'``)
  PYTHONPATH=src python -m backend.aws.sagemaker.cli deploy \\
    --model-data s3://MY_BUCKET/sagemaker/attack-rf/model.tar.gz \\
    --role arn:aws:iam::ACCOUNT:role/SageMakerExecutionRole \\
    --endpoint-name attack-rf-dev

Align local ``scikit-learn`` major/minor with the SageMaker sklearn inference image when possible.
"""

from backend.aws.sagemaker.deploy import default_source_dir, deploy_sklearn_endpoint
from backend.aws.sagemaker.packaging import assert_model_dir_ready, build_model_tarball
from backend.aws.sagemaker.upload import upload_file

__all__ = [
    "assert_model_dir_ready",
    "build_model_tarball",
    "default_source_dir",
    "deploy_sklearn_endpoint",
    "upload_file",
]
