variable "bucket_name" {
  description = "Nom global unique du bucket S3."
  type        = string
}

variable "purpose" {
  description = "Étiquette métier (raw-logs, predictions, …)."
  type        = string
}

variable "enable_versioning" {
  description = "Activer le versioning."
  type        = bool
  default     = true
}

variable "force_destroy" {
  description = "Vider le bucket à la destruction terraform destroy."
  type        = bool
  default     = false
}

variable "prefix_keys" {
  description = "Préfixes logiques à créer (sans slash final)."
  type        = list(string)
  default     = []
}
