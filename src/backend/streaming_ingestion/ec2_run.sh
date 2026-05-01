#!/usr/bin/env bash
# Lance Kafka → S3 sur une instance EC2 (PySpark + IAM instance profile pour S3).
# Prérequis : Java 11/17, pip install pyspark (version alignée avec SPARK_KAFKA_PACKAGES),
# réseau vers les brokers Kafka (ex. MSK en VPC).
#
# Exemple (fichier /etc/default/kafka-streaming ou export manuel) :
#   KAFKA_BOOTSTRAP_SERVERS=b-1.msk....kafka.eu-west-3.amazonaws.com:9092
#   KAFKA_TOPIC=logs-raw
#   S3_OUTPUT_PATH=s3://mon-bucket/raw/kafka/logs/
#   CHECKPOINT_LOCATION=s3://mon-bucket/checkpoints/kafka-logs/
#   AWS_REGION=eu-west-3
#
# systemd : EnvironmentFile=-/etc/default/kafka-streaming
#           ExecStart=/chemin/vers/ec2_run.sh

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_ROOT="$(cd "${HERE}/../.." && pwd)"
export PYTHONPATH="${SRC_ROOT}${PYTHONPATH:+:${PYTHONPATH}}"

if [[ -f /etc/default/kafka-streaming ]]; then
  # shellcheck source=/dev/null
  set -a && source /etc/default/kafka-streaming && set +a
fi

exec python3 "${HERE}/kafka_to_s3.py"
