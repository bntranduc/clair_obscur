from __future__ import annotations

import hashlib
import json
from typing import Any

from backend.worker.config import WorkerConfig
from backend.worker.events import jsonl_gz_to_events, parse_s3_records
from backend.worker.predict_runner import run_predict


def output_key(cfg: WorkerConfig, source_bucket: str, source_key: str) -> str:
    prefix = cfg.output_prefix
    h = hashlib.sha256(f"{source_bucket}/{source_key}".encode()).hexdigest()[:24]
    safe = source_key.replace("/", "_").replace(" ", "_")
    if len(safe) > 180:
        safe = safe[:180]
    return f"{prefix}{h}_{safe}.json"


def process_one_message(
    sqs: Any,
    s3: Any,
    queue_url: str,
    msg: dict[str, Any],
    *,
    cfg: WorkerConfig,
) -> None:
    body = msg.get("Body") or ""
    if not isinstance(body, str):
        body = str(body)
    pairs = parse_s3_records(body)
    if not pairs:
        preview = body[:500].replace("\n", " ")
        raise ValueError(f"no S3 Records in message body (preview: {preview!r})")
    receipt = msg["ReceiptHandle"]

    for bucket, key in pairs:
        obj = s3.get_object(Bucket=bucket, Key=key)
        raw_bytes = obj["Body"].read()
        events = jsonl_gz_to_events(raw_bytes, key=key)
        out_key = output_key(cfg, bucket, key)
        meta = {"source_bucket": bucket, "source_key": key, "event_count": len(events)}

        if not events:
            raise ValueError(
                f"no events parsed from s3://{bucket}/{key}; LLM is required and was not invoked"
            )
        result = run_predict(
            events,
            mode=cfg.predict_mode,
            predict_base=cfg.predict_api_url,
            predict_timeout=cfg.predict_timeout_sec,
            region=cfg.region,
            model_id=cfg.bedrock_model_id,
            max_tokens=cfg.bedrock_max_tokens,
            profile_name=cfg.aws_profile,
        )
        if isinstance(result, dict):
            result = {**result, "meta": meta}
        alerts = result.get("alerts") if isinstance(result, dict) else None
        n_alerts = len(alerts) if isinstance(alerts, list) else 0
        print(
            f"predict s3://{bucket}/{key} events={len(events)} alerts={n_alerts} "
            f"model={cfg.bedrock_model_id or 'default'}",
            flush=True,
        )

        s3.put_object(
            Bucket=cfg.output_bucket,
            Key=out_key,
            Body=json.dumps(result, ensure_ascii=False, indent=2).encode("utf-8"),
            ContentType="application/json",
        )
        print(f"wrote s3://{cfg.output_bucket}/{out_key}", flush=True)

    sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=receipt)
