from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class WorkerConfig:
    queue_url: str
    region: str
    predict_mode: str
    predict_api_url: str
    output_bucket: str
    output_prefix: str
    predict_timeout_sec: int
    sqs_wait_time_seconds: int
    sqs_visibility_timeout: int
    max_sqs_messages: int
    bedrock_model_id: str | None
    bedrock_max_tokens: int
    aws_profile: str | None
    dynamodb_alerts_table: str | None

    @classmethod
    def from_env(cls) -> WorkerConfig:
        queue_url = os.getenv("SQS_QUEUE_URL", "").strip()
        region = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "eu-west-3"))
        prof = (os.getenv("AWS_PROFILE") or "").strip() or None
        mid = (os.getenv("BEDROCK_MODEL_ID") or "").strip() or None
        out_prefix = os.getenv("OUTPUT_PREFIX", "predictions/").strip() or "predictions/"
        if not out_prefix.endswith("/"):
            out_prefix += "/"
        return cls(
            queue_url=queue_url,
            region=region,
            predict_mode=os.getenv("PREDICT_MODE", "inline").strip(),
            predict_api_url=os.getenv("PREDICT_API_URL", "http://127.0.0.1:8080").rstrip("/"),
            output_bucket=os.getenv("OUTPUT_BUCKET", "model-attacks-predictions-tmp").strip(),
            output_prefix=out_prefix,
            predict_timeout_sec=int(os.getenv("PREDICT_TIMEOUT_SEC", "900")),
            sqs_wait_time_seconds=int(os.getenv("SQS_WAIT_TIME_SECONDS", "20")),
            sqs_visibility_timeout=int(os.getenv("SQS_VISIBILITY_TIMEOUT", "900")),
            max_sqs_messages=min(10, max(1, int(os.getenv("MAX_SQS_MESSAGES", "5")))),
            bedrock_model_id=mid,
            bedrock_max_tokens=int(os.getenv("BEDROCK_MAX_TOKENS", "4096")),
            aws_profile=prof,
            dynamodb_alerts_table=(os.getenv("DYNAMODB_ALERTS_TABLE") or "").strip() or None,
        )
