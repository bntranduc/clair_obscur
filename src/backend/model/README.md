# Modèle — API Bedrock (`api.model_app`)

Pipeline : événements normalisés → règles (`detect_signals_window_1h`) → agrégation → Claude via Bedrock → liste d’alertes JSON.

## Sur EC2 (Amazon Linux / même famille)

**Dépannage rapide (SSO expiré, permissions `~/.aws`, Compose)** : voir **`README_EC2.md`** à la racine du dépôt.

Depuis la racine du dépôt (`~/clair_obscur` ou équivalent), après `git pull` :

### 1. Dépendances Python

```bash
cd ~/clair_obscur
python3 -m venv .venv
source .venv/bin/activate
pip install -r src/backend/model/requirements-api.txt
```

Sans venv (moins recommandé) :

```bash
python3 -m pip install --user -r src/backend/model/requirements-api.txt
export PATH="$HOME/.local/bin:$PATH"
```

### 2. Authentification AWS (profil / SSO — pas de clés dans le code)

Le package **`backend.model`** utilise **`boto3`** avec un **`AWS_PROFILE`** optionnel (IAM Identity Center / `aws configure sso`). **Les clés `AWS_ACCESS_KEY_*` ne sont plus passées par le code.**

**En local (recommandé)** :

```bash
aws sso login --profile bao
export AWS_PROFILE=bao
export AWS_REGION=eu-west-3
export AWS_DEFAULT_REGION=eu-west-3
```

(Passe **`bao`** par le nom de ton profil.)

Tu peux aussi mettre `AWS_PROFILE=bao` dans un fichier `.env` à la racine du repo pour les scripts qui font `load_dotenv` (ex. tests). L’API **`api.model_app`** charge ce `.env` au démarrage (comme `api.main`).

**Sur EC2 avec rôle IAM sur l’instance** : ne définis pas `AWS_PROFILE` ; boto3 utilisera automatiquement les credentials du rôle.

Variables optionnelles pour l’API :

- `BEDROCK_MODEL_ID` — sinon défaut dans `bedrock_client.MODEL_ID_DEFAULT`
- `BEDROCK_MAX_TOKENS` — défaut `4096`

Voir `.env.example` à la racine du repo (sans secrets statiques).

### 3. Lancer l’API

```bash
cd ~/clair_obscur
export PYTHONPATH="$PWD/src"
python3 -m uvicorn api.model_app:app --host 0.0.0.0 --port 8080
```

Ou depuis n’importe où sous la racine du repo :

```bash
./src/backend/scripts/run_model_serve.sh
```

**API minimale** (Bedrock uniquement, identifiants dans le corps de `POST /predict`) — peu de dépendances, adaptée EC2 :

```bash
pip install -r src/backend/model/requirements-model-api.txt
./src/backend/model/run_model_api.sh
```

Image Docker : `docker build -f src/backend/model/Dockerfile -t clair-model-api .` puis `docker run --rm -p 8080:8080 -e BEDROCK_MODEL_ID=eu.anthropic.claude-opus-4-6-v1 clair-model-api`.

Exemple `POST /predict` (corps JSON — **ne pas** commiter de vraies clés) :

```bash
curl -sS -X POST http://127.0.0.1:8080/predict -H "Content-Type: application/json" -d @- <<'EOF'
{
  "events": [{"timestamp":"2026-01-15T08:00:01Z","log_source":"authentication","source_ip":"203.0.113.50","auth_method":"ssh","status":"failure","username":"root"}],
  "aws_access_key_id": "AKIA...",
  "aws_secret_access_key": "...",
  "aws_session_token": "IQoJb3...",
  "region": "eu-west-3"
}
EOF
```

(Si `uvicorn` est introuvable : utilise toujours `python3 -m uvicorn` après `pip install -r …`.)

### 4. Sécurité groupe (Security Group)

Autorise le **TCP 8080** (ou le port choisi) **depuis ton IP** (`x.x.x.x/32`) pour tester depuis ton poste. Évite `0.0.0.0/0` en production si possible.

### 5. Tests rapides

Sur l’instance :

```bash
curl -sS http://127.0.0.1:8080/health
```

Depuis ton PC (remplace par l’IP publique de l’instance) :

```bash
curl -sS "http://VOTRE_IP_PUBLIQUE:8080/health"
```

Exemple `POST /predict` (rafale SSH → signal brute force) :

```bash
curl -sS -X POST "http://VOTRE_IP_PUBLIQUE:8080/predict" \
  -H "Content-Type: application/json" \
  -d @- <<'EOF'
{"events":[
  {"timestamp":"2026-01-15T08:00:01Z","log_source":"authentication","source_ip":"203.0.113.50","auth_method":"ssh","status":"failure","username":"root"},
  {"timestamp":"2026-01-15T08:00:02Z","log_source":"authentication","source_ip":"203.0.113.50","auth_method":"ssh","status":"failure","username":"admin"},
  {"timestamp":"2026-01-15T08:00:03Z","log_source":"authentication","source_ip":"203.0.113.50","auth_method":"ssh","status":"failure","username":"ubuntu"},
  {"timestamp":"2026-01-15T08:00:04Z","log_source":"authentication","source_ip":"203.0.113.50","auth_method":"ssh","status":"failure","username":"test"},
  {"timestamp":"2026-01-15T08:00:05Z","log_source":"authentication","source_ip":"203.0.113.50","auth_method":"ssh","status":"failure","username":"oracle"}
]}
EOF
```

Documentation interactive : `http://VOTRE_IP_PUBLIQUE:8080/docs`

Chaque élément de `alerts` inclut `challenge_id`, **`severity`** (`low` \| `medium` \| `high` \| `critical`), **`alert_summary`** (résumé court), `detection`, `detection_time_seconds`, **`confidence`**, **`reasons`**, **`exhaustive_analysis`**, **`remediation_proposal`** (actions opérationnelles proposées). Constante `SEVERITY_LEVELS_SIEM` dans `incident_llm`. Voir `incident_llm.build_prediction_prompt`.

## Fichiers utiles

| Fichier | Rôle |
|--------|------|
| `prompt/expected_predictions_example.json` | Exemple embarqué (ssh_brute_force) injecté dans le prompt Bedrock |
| `prompt/expected_predictions_second_type_example.json` | Deuxième exemple (credential_stuffing) |
| `src/api/model_app.py` | FastAPI complète : `/predict` (Bedrock ; `aws_credentials` optionnel dans le corps), chat, agentic, SIEM |
| `model_api.py` | **API minimale EC2** : `/health`, `/predict` uniquement — Bedrock avec identifiants AWS dans le corps de la requête |
| `Dockerfile` | Image légère : `docker build -f src/backend/model/Dockerfile -t clair-model-api .` (contexte = racine du repo) |
| `requirements-model-api.txt` | Dépendances pour `model_api` / image Docker |
| `run_model_api.sh` | Lance `uvicorn backend.model.model_api:app` en local (`HOST`, `PORT`) |
| `predict.py` | `predict_alerts` → Bedrock (`inline_aws_credentials` ou profil / rôle ; voir `incident_llm`) |
| `../scripts/run_model_serve.sh` | Lance `api.model_app:app` avec `PYTHONPATH` correct |
| `../scripts/sqs_predict_worker.py` | Worker SQS → S3 logs → prédictions → S3 JSON |

Le modèle `.env` versionné est à la racine du repo : `.env.example`.
