output "table_name" {
  description = "Nom de la table."
  value       = aws_dynamodb_table.this.name
}

output "table_arn" {
  description = "ARN de la table."
  value       = aws_dynamodb_table.this.arn
}

output "table_id" {
  description = "Identifiant Terraform de la table."
  value       = aws_dynamodb_table.this.id
}
