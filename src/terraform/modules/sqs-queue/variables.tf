variable "queue_name" {
  description = "Nom de la file SQS principale."
  type        = string
}

variable "purpose" {
  description = "Étiquette métier."
  type        = string
}

variable "visibility_timeout_seconds" {
  description = "Timeout visibilité (aligné sur durée du worker, ex. 900 s)."
  type        = number
  default     = 900
}

variable "message_retention_seconds" {
  description = "Rétention des messages (secondes)."
  type        = number
  default     = 345600
}

variable "receive_wait_time_seconds" {
  description = "Long polling (secondes, max 20)."
  type        = number
  default     = 20
}

variable "max_receive_count" {
  description = "Tentatives avant envoi vers la DLQ."
  type        = number
  default     = 3
}

variable "allow_s3_source_arns" {
  description = "ARNs de buckets S3 autorisés à publier sur la file."
  type        = list(string)
  default     = []
}
