# --- DynamoDB : logs normalisés (alimente dashboard + pipeline prédictions) ---

module "normalized_logs" {
  source = "./modules/dynamodb-table"

  table_name = local.dynamodb_table_name
  purpose    = "normalized-logs"
}
