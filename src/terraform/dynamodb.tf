# --- DynamoDB : logs normalisés (alimente dashboard + pipeline prédictions) ---

module "normalized_logs" {
  source = "./modules/dynamodb-table"

  table_name = local.dynamodb_table_name
  purpose    = "normalized-logs"
}

# --- DynamoDB : alertes (écrites par le worker, lues par l'API) ---

module "alerts" {
  source = "./modules/dynamodb-table"

  table_name = local.dynamodb_alerts_table_name
  purpose    = "alerts"
}

# --- DynamoDB : registre VMs (connexion / approbation admin) ---

module "vm_registry" {
  source = "./modules/dynamodb-table"

  table_name = local.dynamodb_vms_table_name
  purpose    = "vm-registry"
}
