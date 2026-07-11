variable "table_name" {
  description = "Nom de la table DynamoDB."
  type        = string
}

variable "purpose" {
  description = "Étiquette métier (normalized-logs, …)."
  type        = string
}
