# Terraform — CLAIR OBSCUR

Infrastructure AWS par compte développeur (profil IAM local, clés jamais commitées).

## Prérequis

- [Terraform](https://developer.hashicorp.com/terraform/install) ≥ 1.5
- [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
- Utilisateur IAM avec **`AdministratorAccess`** (dev perso) ou policies ciblées

## Setup IAM

1. IAM → **Create user** `clair-obscur-admin` (sans accès console)
2. **Attach policies directly** → `AdministratorAccess`
3. **Security credentials** → **Create access key** (CLI)
4. `aws configure --profile clair-obscur` (region `eu-west-3`)

## Déployer

**Installation complète (recommandé)** — depuis la racine du dépôt :

```bash
cp .env.example .env   # credentials + GIT_REPO_URL
# Activer Bedrock Sonnet dans la console AWS
./deploy-all.sh
```

**Terraform seul** (infra + `.env`, sans attendre les EC2) :

```bash
./scripts/deploy-infra.sh -y
```

Met à jour `.env` automatiquement via `terraform output env_snippet`.

## Structure

```
src/terraform/
├── data.tf              # VPC / subnets / AMI partagés (EC2)
├── versions.tf          # Provider AWS + backend (commenté)
├── variables.tf         # Entrées (profil, région, noms…)
├── locals.tf            # Account ID, noms auto
├── s3.tf                # Buckets logs + prédictions
├── dynamodb.tf          # Tables logs normalisés + alertes + vm-registry
├── sqs.tf               # File SQS + notification S3 → worker
├── ec2_app.tf           # API + frontend
├── ec2_worker.tf        # Worker SQS/Bedrock
├── ec2_demo_vm.tf       # VM capteur démo
├── ec2_fresh_vm.tf      # VM fraîche vm_setup (optionnel)
├── outputs.tf           # Outputs + env_snippet + deployment_summary
├── terraform.tfvars.example
└── modules/
    ├── s3-bucket/
    ├── dynamodb-table/
    └── sqs-queue/
```

## Ressources créées

| Fichier | Ressource | Variable `.env` | Nom auto |
|---------|-----------|-----------------|----------|
| `s3.tf` | Bucket logs bruts | `RAW_LOGS_BUCKET` | `{project}-{account_id}-raw-logs` |
| `s3.tf` | Bucket prédictions JSON | `OUTPUT_BUCKET` | `{project}-{account_id}-predictions` |
| `dynamodb.tf` | Logs normalisés | `DYNAMODB_TABLE` | `{project}-{account_id}-normalized-logs` |
| `dynamodb.tf` | Alertes | `DYNAMODB_ALERTS_TABLE` | `{project}-{account_id}-alerts` |
| `sqs.tf` | File prédictions + DLQ | `SQS_QUEUE_URL` | `{project}-{account_id}-predict` |

Notification S3 : tout `.jsonl` / `.gz` créé sous `RAW_LOGS_PREFIX` → SQS → `backend.worker` (Docker sur EC2).

Schéma DynamoDB (aligné sur le backend) :

| Clé | Type | Exemple |
|-----|------|---------|
| `pk` (hash) | String | `RAW#clair-obscur-904…-raw-logs#D#2026-01-12` |
| `sk` (range) | String | `2026-01-12T10:00:00Z#<uuid>` |

Billing : **PAY_PER_REQUEST** (on-demand, simple en dev).

## Importer S3 → DynamoDB

Après apply et upload des logs :

```bash
# Commenter LOCAL_LOGS_DIR dans .env pour lire DynamoDB/S3 réel
PYTHONPATH=src python3 src/backend/scripts/put_logs_from_s3_to_dynamo_db.py
```

## État Terraform

État **local** (`terraform.tfstate`, gitignored). Chaque dev a son propre état sur son compte.

## Worker prédictions (SQS)

### Option A — EC2 + Docker (Terraform)

`ec2_worker.tf` crée une **t3.micro** qui :

1. `git clone` le dépôt (`worker_git_repo_url` / `worker_git_ref`)
2. `docker build -f src/backend/worker/Dockerfile`
3. Lance le conteneur via **systemd**

```bash
./scripts/deploy-infra.sh -y
# Pusher le code sur GitHub avant le premier boot EC2
```

Mise à jour après un push :

```bash
terraform -chdir=src/terraform output -raw worker_refresh_command | bash
```

Logs : `sudo journalctl -u clair-predict-worker -f` (via SSM)

### Option B — local (dev)

```bash
# Docker
docker build -f src/backend/worker/Dockerfile -t clair-predict-worker .
docker run --rm --env-file .env clair-predict-worker

# Ou Python direct
PYTHONPATH=src python3 -m backend.worker
```

Test : re-upload un `.jsonl` dans le bucket raw logs → message SQS → JSON dans le bucket predictions.

### Option C — EC2 VM démo (capteur + attaques factices)

`ec2_demo_vm.tf` : **t3.micro**, agent `vm_setup/`, nginx `:8080`, envoi S3 `vms/*`.

```bash
terraform output demo_vm_ssm_command
terraform output -raw demo_vm_run_attacks_command | bash
```

Voir [`vm_setup/README.md`](../../vm_setup/README.md).

### Option D — EC2 app (API + frontend)

`ec2_app.tf` : **t3.small**, `docker compose -f docker-compose.prod.yml`

- Pas de `LOCAL_LOGS_DIR` — logs via DynamoDB, alertes via `ALERTS_SOURCE=dynamodb`
- Ports **8020** (API) et **3000** (dashboard) ouverts (CIDR configurable)

```bash
terraform output app_api_url
terraform output app_frontend_url
terraform output -raw app_refresh_command | bash   # apres git push
```

## Prochaines briques

- IAM rôles affinés (least privilege Bedrock par modèle)
- ECS Fargate si scaling horizontal
