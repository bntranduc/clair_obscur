# VM sensor — connexion à CLAIR OBSCUR

Tout ce qu’une VM doit installer pour envoyer des logs vers la pipeline (S3 → SQS → Bedrock → alertes).

## Connexion rapide (recommandé)

L’utilisateur n’a besoin **que du dossier `vm_setup/`**. Pas de credentials AWS requis.

```bash
cd vm_setup
chmod +x connect.sh install.sh
sudo ./connect.sh --api-url http://<IP_APP>:8020 --install
```

Étapes automatiques :
1. Installation de l’agent (nginx démo + collecte logs)
2. Enregistrement auprès de l’API (`POST /api/v1/vms/register`)
3. Attente de l’approbation admin dans le dashboard
4. Envoi des logs via l’API → préfixe S3 dédié par VM

**Dashboard admin** : `http://<IP_APP>:3000/dashboard/vms` — Approuver / Refuser / Révoquer.

## Prérequis VM

- Linux (Amazon Linux 2023, Ubuntu 22+)
- Accès sortant HTTPS vers l’API CLAIR OBSCUR
- **Aucun compte AWS** requis (mode `SHIP_MODE=api`)

## Ce qui est installé

| Composant | Rôle |
|-----------|------|
| **agent** `ship_logs.py` | Lit nginx + auth, JSONL → API ou S3 |
| **systemd** `clair-vm-agent` | Service agent (60s) |
| **nginx** `:8080` | Cible démo (profil `--profile demo`) |
| **`connect.sh`** | Enregistrement + attente approbation |

## Format des logs

Une ligne JSON par événement, schéma aligné sur `src/backend/log/normalization/types.py`.

Destination S3 (après approbation) :

```
s3://<RAW_LOGS_BUCKET>/raw/opensearch/logs-raw/vms/<vm_id>/<vm_id>-<ts>.jsonl
```

→ notification S3 → SQS → worker → DynamoDB alertes → dashboard.

## Installation manuelle (legacy S3 direct)

Pour VMs avec rôle IAM / clés AWS :

```bash
sudo RAW_LOGS_BUCKET=clair-obscur-<account_id>-raw-logs \
     RAW_LOGS_PREFIX=raw/opensearch/logs-raw/ \
     AWS_REGION=eu-west-3 \
     ./install.sh --profile sensor
```

## Fichiers

```
vm_setup/
├── connect.sh              # Connexion à l'app (register + poll)
├── install.sh              # Bootstrap VM (--profile demo|sensor)
├── config/vm-agent.env.example
├── agent/
│   ├── ship_logs.py        # Agent (API ou S3)
│   └── parsers/
└── attacks/
    └── run_fake_attacks.sh
```
