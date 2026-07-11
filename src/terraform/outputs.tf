# --- Compte / région ---

output "aws_region" {
  description = "Région AWS utilisée."
  value       = var.aws_region
}

output "aws_account_id" {
  description = "Compte AWS cible du déploiement."
  value       = data.aws_caller_identity.current.account_id
}

output "aws_profile" {
  description = "Profil AWS CLI utilisé par Terraform."
  value       = var.aws_profile
}

# --- S3 ---

output "raw_logs_bucket_name" {
  description = "Bucket S3 des logs bruts (RAW_LOGS_BUCKET)."
  value       = module.raw_logs.bucket_id
}

output "raw_logs_bucket_arn" {
  description = "ARN du bucket logs bruts."
  value       = module.raw_logs.bucket_arn
}

output "raw_logs_prefix" {
  description = "Préfixe des exports OpenSearch (RAW_LOGS_PREFIX)."
  value       = "${var.raw_logs_prefix}/"
}

output "predictions_bucket_name" {
  description = "Bucket S3 des prédictions (OUTPUT_BUCKET / PREDICTIONS_BUCKET)."
  value       = module.predictions.bucket_id
}

output "predictions_bucket_arn" {
  description = "ARN du bucket prédictions."
  value       = module.predictions.bucket_arn
}

output "predictions_prefix" {
  description = "Préfixe des JSON de prédiction."
  value       = "${var.predictions_prefix}/"
}

# --- DynamoDB ---

output "dynamodb_table_name" {
  description = "Table logs normalisés (DYNAMODB_TABLE)."
  value       = module.normalized_logs.table_name
}

output "dynamodb_table_arn" {
  description = "ARN de la table DynamoDB."
  value       = module.normalized_logs.table_arn
}

output "dynamodb_default_pk" {
  description = "Partition key par défaut pour la démo (DYNAMODB_PK)."
  value       = local.dynamodb_default_pk
}

# --- SQS ---

output "sqs_predict_queue_url" {
  description = "URL file SQS worker (SQS_QUEUE_URL)."
  value       = module.predict_queue.queue_url
}

output "sqs_predict_queue_arn" {
  description = "ARN file SQS prédictions."
  value       = module.predict_queue.queue_arn
}

output "sqs_predict_dlq_url" {
  description = "URL dead-letter queue."
  value       = module.predict_queue.dlq_url
}

# --- EC2 worker ---

output "predict_worker_instance_id" {
  description = "ID instance EC2 worker (null si enable_ec2_worker=false)."
  value       = var.enable_ec2_worker ? aws_instance.predict_worker[0].id : null
}

output "predict_worker_private_ip" {
  description = "IP privée du worker."
  value       = var.enable_ec2_worker ? aws_instance.predict_worker[0].private_ip : null
}

output "worker_ssm_command" {
  description = "Shell sur l'instance via SSM (sans clé SSH)."
  value = var.enable_ec2_worker ? (
    var.aws_profile != "" ?
    "aws ssm start-session --target ${aws_instance.predict_worker[0].id} --region ${var.aws_region} --profile ${var.aws_profile}" :
    "aws ssm start-session --target ${aws_instance.predict_worker[0].id} --region ${var.aws_region}"
  ) : null
}

output "worker_refresh_command" {
  description = "Met a jour le worker sur l'EC2 : git pull + rebuild Docker (via SSM)."
  value = var.enable_ec2_worker ? (
    var.aws_profile != "" ?
    "aws ssm send-command --instance-ids ${aws_instance.predict_worker[0].id} --document-name AWS-RunShellScript --parameters 'commands=[\"cd /opt/clair-obscur && git pull && docker build -f src/backend/worker/Dockerfile -t clair-predict-worker . && systemctl restart clair-predict-worker\"]' --region ${var.aws_region} --profile ${var.aws_profile}" :
    "aws ssm send-command --instance-ids ${aws_instance.predict_worker[0].id} --document-name AWS-RunShellScript --parameters 'commands=[\"cd /opt/clair-obscur && git pull && docker build -f src/backend/worker/Dockerfile -t clair-predict-worker . && systemctl restart clair-predict-worker\"]' --region ${var.aws_region}"
  ) : null
}

# --- .env ---

output "env_snippet" {
  description = "Variables à copier dans .env après apply."
  value       = <<-EOT
    AWS_PROFILE=${var.aws_profile}
    AWS_REGION=${var.aws_region}
    AWS_DEFAULT_REGION=${var.aws_region}
    RAW_LOGS_BUCKET=${module.raw_logs.bucket_id}
    RAW_LOGS_PREFIX=${var.raw_logs_prefix}/
    PREDICTIONS_BUCKET=${module.predictions.bucket_id}
    PREDICTIONS_PREFIX=${var.predictions_prefix}/
    OUTPUT_BUCKET=${module.predictions.bucket_id}
    OUTPUT_PREFIX=${var.predictions_prefix}/
    DYNAMODB_TABLE=${module.normalized_logs.table_name}
    DYNAMODB_PK=${local.dynamodb_default_pk}
    SQS_QUEUE_URL=${module.predict_queue.queue_url}
    SQS_VISIBILITY_TIMEOUT=${var.sqs_visibility_timeout_seconds}
    PREDICT_MODE=inline
    BEDROCK_MODEL_ID=${var.worker_bedrock_model_id}
  EOT
}
