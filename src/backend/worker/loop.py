from __future__ import annotations

import sys
import time
import urllib.error

from backend.aws.aws_client import AwsClient
from backend.worker.config import WorkerConfig
from backend.worker.processor import process_one_message


def main() -> int:
    cfg = WorkerConfig.from_env()
    if not cfg.queue_url:
        print("SQS_QUEUE_URL is required", file=sys.stderr)
        return 1

    aws = AwsClient.for_env(region_name=cfg.region)
    sqs = aws.client("sqs")
    s3 = aws.client("s3")

    print(
        f"worker start queue={cfg.queue_url!r} mode={cfg.predict_mode!r} "
        f"out={cfg.output_bucket} region={cfg.region}",
        flush=True,
    )
    while True:
        resp = sqs.receive_message(
            QueueUrl=cfg.queue_url,
            MaxNumberOfMessages=cfg.max_sqs_messages,
            WaitTimeSeconds=min(20, max(0, cfg.sqs_wait_time_seconds)),
            VisibilityTimeout=min(43200, max(0, cfg.sqs_visibility_timeout)),
            AttributeNames=["All"],
        )
        messages = resp.get("Messages") or []
        if not messages:
            continue
        for msg in messages:
            try:
                process_one_message(sqs, s3, cfg.queue_url, msg, cfg=cfg)
            except ValueError as e:
                print(f"error: {e}", file=sys.stderr)
                if "no S3 Records" in str(e):
                    receipt = msg.get("ReceiptHandle")
                    if receipt:
                        sqs.delete_message(QueueUrl=cfg.queue_url, ReceiptHandle=receipt)
                        print("skipped invalid message (deleted)", file=sys.stderr)
                else:
                    raise
            except RuntimeError as e:
                print(f"LLM error: {e}", file=sys.stderr)
                print("message left for retry after visibility timeout", file=sys.stderr)
                time.sleep(2)
            except urllib.error.HTTPError as e:
                print(e.read().decode("utf-8", errors="replace"), file=sys.stderr)
                print("HTTP error, message left for retry", file=sys.stderr)
            except Exception as e:
                print(f"error: {e}", file=sys.stderr)
                time.sleep(2)
