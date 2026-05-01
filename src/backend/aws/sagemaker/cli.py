#!/usr/bin/env python3
"""CLI: package local model → upload S3 → (optional) deploy SageMaker endpoint."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from backend.aws.sagemaker.deploy import default_source_dir, deploy_sklearn_endpoint
from backend.aws.sagemaker.packaging import build_model_tarball
from backend.aws.sagemaker.upload import upload_file


def _cmd_package(ap: argparse.ArgumentParser) -> None:
    ap.add_argument("--model-dir", type=Path, required=True)
    ap.add_argument("-o", "--output", type=Path, required=True, help="e.g. ./model.tar.gz")


def _cmd_upload(ap: argparse.ArgumentParser) -> None:
    ap.add_argument("--file", type=Path, required=True)
    ap.add_argument("--bucket", required=True)
    ap.add_argument("--key", required=True, help="S3 object key (no s3:// prefix)")
    ap.add_argument("--region", default=os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION"))


def _cmd_deploy(ap: argparse.ArgumentParser) -> None:
    ap.add_argument("--model-data", required=True, help="s3://bucket/path/model.tar.gz")
    ap.add_argument("--role", required=True, help="SageMaker execution role ARN")
    ap.add_argument("--endpoint-name", required=True)
    ap.add_argument("--instance-type", default="ml.m5.large")
    ap.add_argument("--framework-version", default="1.2-1")
    ap.add_argument("--py-version", default="py3")
    ap.add_argument("--source-dir", type=Path, default=None, help="Default: repo src/")
    ap.add_argument("--region", default=os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION"))


def main() -> int:
    parser = argparse.ArgumentParser(description="SageMaker helpers for attack_predictor")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_pkg = sub.add_parser("package", help="Build model.tar.gz from local train output")
    _cmd_package(p_pkg)

    p_up = sub.add_parser("upload", help="Upload tarball to S3")
    _cmd_upload(p_up)

    p_dep = sub.add_parser("deploy", help="Deploy SKLearnModel endpoint (needs sagemaker SDK)")
    _cmd_deploy(p_dep)

    p_all = sub.add_parser(
        "package-upload",
        help="package + upload in one step",
    )
    _cmd_package(p_all)
    p_all.add_argument("--bucket", required=True)
    p_all.add_argument("--key", required=True)
    p_all.add_argument("--region", default=os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION"))

    args = parser.parse_args()

    if args.cmd == "package":
        out = build_model_tarball(args.model_dir, args.output)
        print(out)
        return 0

    if args.cmd == "upload":
        uri = upload_file(
            args.file,
            bucket=args.bucket,
            key=args.key,
            region=args.region,
        )
        print(uri)
        return 0

    if args.cmd == "package-upload":
        out_tar = args.output
        if not str(out_tar).endswith(".tar.gz"):
            out_tar = out_tar.with_suffix(".tar.gz") if out_tar.suffix else Path(str(out_tar) + ".tar.gz")
        build_model_tarball(args.model_dir, out_tar)
        uri = upload_file(out_tar, bucket=args.bucket, key=args.key, region=args.region)
        print(uri)
        return 0

    if args.cmd == "deploy":
        src = args.source_dir or default_source_dir()
        predictor = deploy_sklearn_endpoint(
            model_data=args.model_data,
            role=args.role,
            endpoint_name=args.endpoint_name,
            instance_type=args.instance_type,
            framework_version=args.framework_version,
            py_version=args.py_version,
            source_dir=src,
            region=args.region,
        )
        print(predictor.endpoint_name)
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
