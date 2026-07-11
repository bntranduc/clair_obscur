# CLAIR OBSCUR

Plateforme NDR/SOC : détection d’attaques (règles + Bedrock), dashboard analyste, assistant agentique.

## Démarrage rapide (backend local, sans AWS)

```bash
# 1. Environnement Python
chmod +x scripts/setup-dev.sh src/api/run.sh
./scripts/setup-dev.sh
source .venv/bin/activate

# 2. Si Docker occupe le port 8020
docker compose down

# 3. Lancer l’API
./src/api/run.sh
```

Vérification :

```bash
curl http://127.0.0.1:8020/health
curl http://127.0.0.1:8020/api/v1/alerts | head -c 200
curl "http://127.0.0.1:8020/api/v1/logs/dynamodb?limit=5"
```

Sans credentials AWS, les logs et analytics viennent de `data/sample_logs/demo.jsonl` (`LOCAL_LOGS_DIR` dans `.env`).

| Endpoint | Source locale |
|---|---|
| `GET /api/v1/alerts` | `database/alerts.json` |
| `GET /api/v1/logs/dynamodb` | `LOCAL_LOGS_DIR` (JSONL) |
| `GET /api/v1/analytics/dynamodb` | idem |
| `GET /api/v1/analytics/siem` | OpenSearch ou repli **demo** |
| `GET /api/v1/alerts/clustering` | `database/alerts.json` |

## Docker (backend + frontend)

```bash
cp .env.example .env
docker compose up --build
```

- Frontend : http://localhost:3000  
- API : http://localhost:8020  

## Structure

```
src/
├── api/          # FastAPI dashboard (port 8020)
├── backend/      # Pipeline détection, agentic, AWS, analytics
└── frontend/     # Next.js 16 dashboard (port 3000)
data/sample_logs/ # Logs JSONL de démo (mode local)
database/
└── alerts.json   # Catalogue d’alertes
```

## Déployer l'infra AWS (S3 + DynamoDB + SQS + EC2 worker + EC2 app)

```bash
aws configure --profile clair-obscur   # clés IAM
cp src/terraform/terraform.tfvars.example src/terraform/terraform.tfvars
chmod +x scripts/deploy-infra.sh
./scripts/deploy-infra.sh
```

- **Worker** : SQS → Bedrock → S3 predictions (EC2 dédiée)
- **App** : API `:8020` + frontend `:3000` (`docker-compose.prod.yml`, alertes depuis S3, logs DynamoDB)

Voir `src/terraform/README.md` pour le détail.

## Scripts opérationnels

| Script | Usage |
|--------|--------|
| `scripts/setup-dev.sh` | venv + pip install + `.env` |
| `scripts/deploy-infra.sh` | Terraform S3 + DynamoDB + `.env` |
| `scripts/deploy-s3.sh` | Alias de `deploy-infra.sh` |
| `src/api/run.sh` | Lance uvicorn en local |
| `src/backend/scripts/run_ingestion_to_alerts.py` | JSONL → alertes |
| `src/backend/worker/` | Worker SQS (code + Dockerfile) |
| `src/backend/scripts/sqs_predict_worker.py` | Alias CLI worker |

## Variables d’environnement

Voir `.env.example`. Clé locale : **`LOCAL_LOGS_DIR=data/sample_logs`**.

Pour brancher l’AWS réel : `./scripts/deploy-s3.sh`, puis retirer ou commenter `LOCAL_LOGS_DIR`, configurer `DYNAMODB_PK`, OpenSearch.
