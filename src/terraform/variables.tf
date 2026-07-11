variable "aws_region" {
  description = "Région AWS (ex. eu-west-3)."
  type        = string
  default     = "eu-west-3"
}

variable "aws_profile" {
  description = "Profil ~/.aws/credentials (aws configure --profile …). Vide = profil par défaut ou variables d'environnement."
  type        = string
  default     = "clair-obscur"
}

variable "project_name" {
  description = "Préfixe de nommage des ressources (ex. clair-obscur)."
  type        = string
  default     = "clair-obscur"
}

variable "environment" {
  description = "Environnement (dev, staging, prod)."
  type        = string
  default     = "dev"
}

variable "enable_versioning" {
  description = "Activer le versioning S3 sur les buckets applicatifs."
  type        = bool
  default     = true
}

variable "force_destroy" {
  description = "Autoriser la destruction des buckets même s'ils contiennent des objets (dev uniquement)."
  type        = bool
  default     = false
}

variable "raw_logs_bucket_name" {
  description = "Nom global du bucket logs bruts. Vide = généré (project-account_id-raw-logs)."
  type        = string
  default     = ""
}

variable "predictions_bucket_name" {
  description = "Nom global du bucket prédictions / alertes JSON. Vide = généré (project-account_id-predictions)."
  type        = string
  default     = ""
}

variable "raw_logs_prefix" {
  description = "Préfixe S3 des exports OpenSearch (sans slash final)."
  type        = string
  default     = "raw/opensearch/logs-raw"
}

variable "predictions_prefix" {
  description = "Préfixe S3 des fichiers de prédiction."
  type        = string
  default     = "predictions"
}

variable "dynamodb_table_name" {
  description = "Nom table DynamoDB logs normalisés. Vide = clair-obscur-<account_id>-normalized-logs."
  type        = string
  default     = ""
}

variable "dynamodb_alerts_table_name" {
  description = "Nom table DynamoDB alertes. Vide = clair-obscur-<account_id>-alerts."
  type        = string
  default     = ""
}

variable "dynamodb_demo_day" {
  description = "Jour ISO (YYYY-MM-DD) pour DYNAMODB_PK par défaut (aligné sur demo.jsonl)."
  type        = string
  default     = "2026-01-12"
}

variable "sqs_queue_name" {
  description = "Nom file SQS prédictions. Vide = clair-obscur-<account_id>-predict."
  type        = string
  default     = ""
}

variable "sqs_visibility_timeout_seconds" {
  description = "Timeout visibilité SQS (≥ durée worker Bedrock)."
  type        = number
  default     = 900
}

variable "sqs_message_retention_seconds" {
  description = "Rétention messages SQS (secondes)."
  type        = number
  default     = 345600
}

variable "sqs_receive_wait_time_seconds" {
  description = "Long polling SQS (secondes)."
  type        = number
  default     = 20
}

variable "sqs_max_receive_count" {
  description = "Retries avant dead-letter queue."
  type        = number
  default     = 3
}

variable "enable_ec2_worker" {
  description = "Créer l'instance EC2 worker (SQS long polling)."
  type        = bool
  default     = true
}

variable "worker_instance_type" {
  description = "Type d'instance EC2 pour le worker."
  type        = string
  default     = "t3.small"
}

variable "worker_bedrock_model_id" {
  description = "Modèle Bedrock (inline) sur l'instance."
  type        = string
  default     = "eu.anthropic.claude-sonnet-4-6"
}

variable "worker_key_name" {
  description = "Nom de clé SSH EC2 (optionnel). Laisse vide : accès via SSM Session Manager."
  type        = string
  default     = ""
}

variable "worker_git_repo_url" {
  description = "URL git du dépôt clair_obscur (HTTPS). Repo public ou token dans l'URL."
  type        = string
  default     = "https://github.com/bntranduc/clair_obscur.git"
}

variable "worker_git_ref" {
  description = "Branche ou tag à déployer sur l'EC2 worker."
  type        = string
  default     = "main"
}

variable "enable_ec2_app" {
  description = "Créer l'instance EC2 API + frontend (docker compose prod)."
  type        = bool
  default     = true
}

variable "app_instance_type" {
  description = "Type d'instance EC2 pour l'API + frontend."
  type        = string
  default     = "t2.medium"
}

variable "app_ingress_cidr_blocks" {
  description = "CIDR autorises sur les ports 8020 et 3000."
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "enable_ec2_demo_vm" {
  description = "Créer une EC2 VM démo (capteur logs + attaques factices)."
  type        = bool
  default     = true
}

variable "demo_vm_instance_type" {
  description = "Type d'instance pour la VM démo capteur."
  type        = string
  default     = "t3.micro"
}

variable "demo_vm_ingress_cidr_blocks" {
  description = "CIDR autorises sur nginx 8080 (cible attaques)."
  type        = list(string)
  default     = ["0.0.0.0/0"]
}
