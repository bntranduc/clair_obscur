output "bucket_id" {
  description = "Nom (ID) du bucket."
  value       = aws_s3_bucket.this.id
}

output "bucket_arn" {
  description = "ARN du bucket."
  value       = aws_s3_bucket.this.arn
}

output "bucket_domain_name" {
  description = "Nom de domaine bucket (endpoint régional)."
  value       = aws_s3_bucket.this.bucket_regional_domain_name
}
