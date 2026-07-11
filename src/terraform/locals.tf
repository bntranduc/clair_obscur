data "aws_caller_identity" "current" {}

locals {
  account_suffix = data.aws_caller_identity.current.account_id

  raw_logs_bucket_name = coalesce(
    var.raw_logs_bucket_name != "" ? var.raw_logs_bucket_name : null,
    "${var.project_name}-${local.account_suffix}-raw-logs",
  )

  predictions_bucket_name = coalesce(
    var.predictions_bucket_name != "" ? var.predictions_bucket_name : null,
    "${var.project_name}-${local.account_suffix}-predictions",
  )

  dynamodb_table_name = coalesce(
    var.dynamodb_table_name != "" ? var.dynamodb_table_name : null,
    "${var.project_name}-${local.account_suffix}-normalized-logs",
  )

  dynamodb_alerts_table_name = coalesce(
    var.dynamodb_alerts_table_name != "" ? var.dynamodb_alerts_table_name : null,
    "${var.project_name}-${local.account_suffix}-alerts",
  )

  dynamodb_alerts_default_pk = "ALERTS"

  # Partition par défaut pour la démo (demo.jsonl → jour 2026-01-12).
  dynamodb_default_pk = "RAW#${local.raw_logs_bucket_name}#D#${var.dynamodb_demo_day}"

  sqs_predict_queue_name = coalesce(
    var.sqs_queue_name != "" ? var.sqs_queue_name : null,
    "${var.project_name}-${local.account_suffix}-predict",
  )
}
