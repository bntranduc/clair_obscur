# --- S3 : logs bruts + prédictions (JSON) ---

module "raw_logs" {
  source = "./modules/s3-bucket"

  bucket_name       = local.raw_logs_bucket_name
  purpose           = "raw-logs"
  enable_versioning = var.enable_versioning
  force_destroy     = var.force_destroy
  prefix_keys       = [var.raw_logs_prefix]
}

module "predictions" {
  source = "./modules/s3-bucket"

  bucket_name       = local.predictions_bucket_name
  purpose           = "predictions"
  enable_versioning = var.enable_versioning
  force_destroy     = var.force_destroy
  prefix_keys       = [var.predictions_prefix]
}
