#!/usr/bin/env python3
"""
Lance le job Spark Structured Streaming Kafka → S3 (`backend.streaming_ingestion.kafka_to_s3`).

Usage local (avec PySpark installé + broker Kafka joignable) :
  export KAFKA_BOOTSTRAP_SERVERS=localhost:9092
  export KAFKA_TOPIC=logs-raw
  export S3_OUTPUT_PATH=s3a://bucket/prefix/kafka/
  export CHECKPOINT_LOCATION=s3a://bucket/checkpoints/kafka-logs/
  PYTHONPATH=src python3 src/backend/scripts/run_kafka_to_s3_streaming.py

Sur AWS :
  - EMR : `spark-submit` avec `--packages` Kafka (voir doc du module).
  - EC2 : IAM instance profile + `src/backend/streaming_ingestion/ec2_run.sh`
    (export `KAFKA_*`, `S3_OUTPUT_PATH`, `CHECKPOINT_LOCATION`, `AWS_REGION`).
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from backend.streaming_ingestion.kafka_to_s3 import main

if __name__ == "__main__":
    main()
