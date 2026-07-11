# --- SQS : notifications S3 (nouveau log) → worker prédictions ---

module "predict_queue" {
  source = "./modules/sqs-queue"

  queue_name                 = local.sqs_predict_queue_name
  purpose                    = "s3-predict-worker"
  visibility_timeout_seconds = var.sqs_visibility_timeout_seconds
  message_retention_seconds  = var.sqs_message_retention_seconds
  receive_wait_time_seconds  = var.sqs_receive_wait_time_seconds
  max_receive_count          = var.sqs_max_receive_count
  allow_s3_source_arns       = [module.raw_logs.bucket_arn]
}

resource "aws_s3_bucket_notification" "raw_logs_to_predict_queue" {
  bucket = module.raw_logs.bucket_id

  queue {
    queue_arn     = module.predict_queue.queue_arn
    events        = ["s3:ObjectCreated:*"]
    filter_prefix = "${var.raw_logs_prefix}/"
    filter_suffix = ".jsonl"
  }

  queue {
    queue_arn     = module.predict_queue.queue_arn
    events        = ["s3:ObjectCreated:*"]
    filter_prefix = "${var.raw_logs_prefix}/"
    filter_suffix = ".gz"
  }

  depends_on = [module.predict_queue]
}
