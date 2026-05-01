"""
SageMaker Model Upload & Deployment Script

Usage:
    # 1. Package the model (run from attack_predictor directory)
    tar -czf model.tar.gz predictor.py inference.py features.py labels.py *.joblib metadata.json

    # 2. Deploy to SageMaker
    python upload_to_sagemaker.py --bucket clair-obscure-raw-logs --model-path model.tar.gz
"""

import argparse
import json
from pathlib import Path

import boto3
from sagemaker.sklearn.model import SKLearnModel

# Configuration
BUCKET = "clair-obscure-raw-logs"
S3_KEY = "attack/model.tar.gz"
ROLE_ARN = "arn:aws:iam::role:role/SageMakerExecutionRole"
INSTANCE_TYPE = "ml.m5.large"
INITIAL_INSTANCE_COUNT = 1
FRAMEWORK_VERSION = "1.2-1"


def upload_model_to_s3(bucket: str, local_path: str, s3_key: str) -> str:
    """Upload model.tar.gz to S3 and return s3_uri."""
    s3_client = boto3.client("s3")
    
    print(f"Uploading {local_path} to s3://{bucket}/{s3_key}...")
    s3_client.upload_file(local_path, bucket, s3_key)
    
    s3_uri = f"s3://{bucket}/{s3_key}"
    print(f"✓ Model uploaded to {s3_uri}")
    return s3_uri


def deploy_model(
    model_s3_uri: str,
    role_arn: str,
    bucket: str,
    instance_type: str = INSTANCE_TYPE,
    initial_instance_count: int = INITIAL_INSTANCE_COUNT,
) -> dict[str, str]:
    """Create and deploy SageMaker endpoint."""
    
    model = SKLearnModel(
        model_data=model_s3_uri,
        role=role_arn,
        entry_point="inference.py",
        framework_version=FRAMEWORK_VERSION,
        source_dir=".",
    )
    
    print(f"Deploying model on {instance_type}...")
    predictor = model.deploy(
        instance_type=instance_type,
        initial_instance_count=initial_instance_count,
    )
    
    endpoint_name = predictor.endpoint_name
    print(f"✓ Endpoint deployed: {endpoint_name}")
    
    # Save endpoint info
    endpoint_info = {
        "endpoint_name": endpoint_name,
        "model_s3_uri": model_s3_uri,
        "instance_type": instance_type,
        "created_at": str(Path.cwd()),
    }
    
    with open("endpoint_config.json", "w") as f:
        json.dump(endpoint_info, f, indent=2)
    
    print(f"Endpoint config saved to endpoint_config.json")
    
    return endpoint_info


def main():
    parser = argparse.ArgumentParser(description="Upload and deploy model to SageMaker")
    parser.add_argument(
        "--bucket",
        default=BUCKET,
        help=f"S3 bucket name (default: {BUCKET})",
    )
    parser.add_argument(
        "--model-path",
        required=True,
        help="Local path to model.tar.gz",
    )
    parser.add_argument(
        "--role-arn",
        required=True,
        help="IAM role ARN for SageMaker",
    )
    parser.add_argument(
        "--s3-key",
        default=S3_KEY,
        help=f"S3 key for model (default: {S3_KEY})",
    )
    parser.add_argument(
        "--instance-type",
        default=INSTANCE_TYPE,
        help=f"SageMaker instance type (default: {INSTANCE_TYPE})",
    )
    parser.add_argument(
        "--instance-count",
        type=int,
        default=INITIAL_INSTANCE_COUNT,
        help=f"Number of instances (default: {INITIAL_INSTANCE_COUNT})",
    )
    
    args = parser.parse_args()
    
    # Validate model file exists
    model_path = Path(args.model_path)
    if not model_path.exists():
        raise FileNotFoundError(f"Model file not found: {args.model_path}")
    
    # Upload to S3
    s3_uri = upload_model_to_s3(args.bucket, args.model_path, args.s3_key)
    
    # Deploy to SageMaker
    endpoint_info = deploy_model(
        s3_uri,
        args.role_arn,
        args.bucket,
        instance_type=args.instance_type,
        initial_instance_count=args.instance_count,
    )
    
    print("\n" + "="*50)
    print("Deployment successful!")
    print(f"Endpoint Name: {endpoint_info['endpoint_name']}")
    print("="*50)


if __name__ == "__main__":
    main()