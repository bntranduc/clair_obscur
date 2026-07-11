output "queue_name" {
  description = "Nom de la file principale."
  value       = aws_sqs_queue.this.name
}

output "queue_arn" {
  description = "ARN de la file principale."
  value       = aws_sqs_queue.this.arn
}

output "queue_url" {
  description = "URL de la file principale (SQS_QUEUE_URL)."
  value       = aws_sqs_queue.this.url
}

output "dlq_arn" {
  description = "ARN de la dead-letter queue."
  value       = aws_sqs_queue.dlq.arn
}

output "dlq_url" {
  description = "URL de la dead-letter queue."
  value       = aws_sqs_queue.dlq.url
}
