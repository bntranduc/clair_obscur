# VM sensor — connexion à CLAIR OBSCUR

Tout ce qu’une VM doit installer pour envoyer des logs vers la pipeline (S3 → SQS → Bedrock → alertes).

## Prérequis VM

- Linux (Amazon Linux 2023, Ubuntu 22+)
- Accès sortant HTTPS (S3)
- Credentials AWS avec `s3:PutObject` sur `raw/opensearch/logs-raw/vms/*`
  - Sur l’EC2 démo Terraform : **rôle IAM instance** (automatique)
  - VM externe : IAM user + clés dans `/etc/clair-obscur/vm-agent.env` ou `aws configure`

## Installation (VM quelconque)

```bash
git clone https://github.com/bntranduc/clair_obscur.git
cd clair_obscur/vm_setup

sudo RAW_LOGS_BUCKET=clair-obscur-<account_id>-raw-logs \
     RAW_LOGS_PREFIX=raw/opensearch/logs-raw/ \
     AWS_REGION=eu-west-3 \
     ./install.sh
```

Ou après édition de `config/vm-agent.env.example` → `/etc/clair-obscur/vm-agent.env` :

```bash
sudo ./install.sh
```

## Ce qui est installé

| Composant | Rôle |
|-----------|------|
| **nginx** `:8080` | Cible HTTP pour attaques factices |
| **agent** `ship_logs.py` | Lit nginx + auth, JSONL → S3 toutes les 60s |
| **systemd** `clair-vm-agent` | Service agent |
| **`clair-run-fake-attacks`** | Script d’attaques factices |

## Format des logs envoyés

Une ligne JSON par événement, schéma aligné sur `src/backend/log/normalization/types.py` :

- `log_source`: `application` (nginx) ou `authentication` (sshd)
- `timestamp`: ISO 8601 UTC
- champs selon le type (voir `data/sample_logs/demo.jsonl`)

Destination S3 :

```
s3://<RAW_LOGS_BUCKET>/raw/opensearch/logs-raw/vms/<hostname>/<hostname>-<ts>.jsonl
```

→ notification S3 → SQS → worker → DynamoDB alertes → dashboard.

## Tester les attaques factices

```bash
# Sur la VM
sudo clair-run-fake-attacks
sudo python3 /opt/clair-vm-agent/ship_logs.py

# EC2 démo Terraform (depuis ta machine)
terraform -chdir=src/terraform output -raw demo_vm_run_attacks_command | bash
terraform -chdir=src/terraform output demo_vm_ssm_command
```

## Fichiers

```
vm_setup/
├── install.sh              # Bootstrap VM
├── config/vm-agent.env.example
├── agent/
│   ├── ship_logs.py        # Agent principal
│   └── parsers/            # nginx, auth
└── attacks/
    └── run_fake_attacks.sh
```
