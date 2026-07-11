# CLAIR OBSCUR

Plateforme NDR/SOC : détection d’attaques (règles + Bedrock), dashboard analyste, assistant agentique.

---

## Installation prod (machine fraîche → dashboard en ligne)

### Prérequis système

```bash
# Ubuntu / Debian
sudo apt update
sudo apt install -y awscli terraform git python3 curl unzip

# Vérifier
aws --version && terraform version
```

### 3 étapes

**1. Credentials et config**

```bash
git clone https://github.com/bntranduc/clair_obscur.git
cd clair_obscur
cp .env.example .env
```

Éditer `.env` :

| Variable | Description |
|----------|-------------|
| `AWS_PROFILE` | Profil CLI (`aws configure --profile clair-obscur`) **ou** laisser vide et mettre `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` |
| `AWS_REGION` | `eu-west-3` |
| `GIT_REPO_URL` | URL HTTPS du dépôt cloné sur les EC2 (public ou token dans l’URL) |
| `GIT_REF` | Branche à déployer (`main`) |
| `BEDROCK_MODEL_ID` | `eu.anthropic.claude-sonnet-4-6` |

**2. Activer Bedrock** (une fois par compte AWS)

Console AWS → **Amazon Bedrock** → **Model access** → activer **Claude Sonnet 4.6** en `eu-west-3`.

**3. Lancer l’installation**

```bash
chmod +x scripts/install.sh
./scripts/install.sh
```

Le script enchaîne automatiquement :

```
Vérif AWS + Bedrock
    → terraform apply (S3, DynamoDB×2, SQS, EC2 worker, EC2 app)
    → sync .env
    → déploiement worker (Docker + SQS + Bedrock → DynamoDB alertes)
    → déploiement app (API :8020 + frontend :3000)
    → upload demo.jsonl (optionnel)
    → affiche les URLs du dashboard
```

Durée totale : **~15–25 min** (build Next.js sur EC2).

Options dans `.env` :

```bash
INSTALL_UPLOAD_DEMO=0      # ne pas uploader demo.jsonl
INSTALL_GIT_PUSH=1         # git push avant deploy si commits locaux
WORKER_INSTANCE_TYPE=t3.small
APP_INSTANCE_TYPE=t2.medium
```

---

## Architecture prod

```
Upload .jsonl → S3 → SQS → EC2 worker → Bedrock
                              ↓
                    S3 predictions (audit)
                              ↓
                    DynamoDB alerts → API → Dashboard
```

| Composant | Rôle |
|-----------|------|
| S3 raw-logs | Entrée pipeline (`.jsonl`) |
| EC2 worker | SQS → Bedrock → DynamoDB alertes |
| DynamoDB alerts | Source dashboard alertes |
| DynamoDB normalized-logs | Onglet Logs (script séparé) |
| EC2 app | API `:8020` + frontend `:3000` |

---

## Dev local (sans AWS)

```bash
chmod +x scripts/setup-dev.sh src/api/run.sh
./scripts/setup-dev.sh
source .venv/bin/activate
./src/api/run.sh
```

Alertes : `database/alerts.json` · Logs : `data/sample_logs/demo.jsonl`

Docker local : `cp .env.example .env && docker compose up --build`

---

## Tester la pipeline après install

```bash
set -a && source .env && set +a

aws s3 cp database/multi_alerts_test.jsonl \
  "s3://${RAW_LOGS_BUCKET}/raw/opensearch/logs-raw/test-$(date +%s).jsonl" \
  --region "$AWS_REGION" ${AWS_PROFILE:+--profile $AWS_PROFILE}
```

Attendre ~1 min → rafraîchir le dashboard (`F5`).

Vérifier :

```bash
IP=$(terraform -chdir=src/terraform output -raw app_public_ip)
curl -s "http://${IP}:8020/health" | python3 -m json.tool
# → alerts_source: dynamodb, local_logs_dir: null
```

---

## Mise à jour après un `git push`

```bash
terraform -chdir=src/terraform output -raw worker_refresh_command | bash
terraform -chdir=src/terraform output -raw app_refresh_command | bash
```

---

## Scripts

| Script | Usage |
|--------|--------|
| **`scripts/install.sh`** | **Installation complète (recommandé)** |
| `scripts/setup-dev.sh` | Dev local Python |
| `scripts/deploy-infra.sh` | Terraform seul + sync `.env` |
| `scripts/ec2-refresh-worker.sh` | Rebuild worker (sur EC2) |
| `scripts/ec2-refresh-app.sh` | Rebuild API + frontend (sur EC2) |
| `put_logs_from_s3_to_dynamo_db.py` | Alimenter onglet Logs |
| `put_alerts_from_s3_to_dynamo_db.py` | Backfill alertes S3 → DynamoDB |

## VM capteur (logs → S3)

Voir [`vm_setup/README.md`](vm_setup/README.md) — agent, attaques factices, EC2 démo.

```bash
terraform -chdir=src/terraform output -raw demo_vm_run_attacks_command | bash
```

---

## Structure

```
src/api/           FastAPI (:8020)
src/backend/worker/  Worker SQS + Bedrock
src/frontend/      Next.js (:3000)
src/terraform/     Infra AWS
database/          alerts.json (dev) + multi_alerts_test.jsonl
data/sample_logs/  demo.jsonl
```

Détail Terraform : [`src/terraform/README.md`](src/terraform/README.md)

---

## Sécurité (POC)

- HTTP public sur ports 8020 / 3000
- Ne pas committer `.env`, `terraform.tfvars`, clés AWS
- Rotater toute clé exposée accidentellement
