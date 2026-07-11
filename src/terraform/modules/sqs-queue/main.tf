resource "aws_sqs_queue" "dlq" {
  name                      = "${var.queue_name}-dlq"
  message_retention_seconds = var.message_retention_seconds

  tags = {
    Name    = "${var.queue_name}-dlq"
    Purpose = var.purpose
  }
}

resource "aws_sqs_queue" "this" {
  name                       = var.queue_name
  visibility_timeout_seconds = var.visibility_timeout_seconds
  message_retention_seconds  = var.message_retention_seconds
  receive_wait_time_seconds  = var.receive_wait_time_seconds

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq.arn
    maxReceiveCount     = var.max_receive_count
  })

  tags = {
    Name    = var.queue_name
    Purpose = var.purpose
  }
}

resource "aws_sqs_queue_policy" "this" {
  count     = length(var.allow_s3_source_arns) > 0 ? 1 : 0
  queue_url = aws_sqs_queue.this.url

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      for arn in var.allow_s3_source_arns : {
        Sid       = "AllowS3SendMessage"
        Effect    = "Allow"
        Principal = { Service = "s3.amazonaws.com" }
        Action    = "sqs:SendMessage"
        Resource  = aws_sqs_queue.this.arn
        Condition = {
          ArnEquals = {
            "aws:SourceArn" = arn
          }
        }
      }
    ]
  })
}
