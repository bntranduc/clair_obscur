# Modèle — API Bedrock (`serve_app`)

Pipeline : événements normalisés → règles (`detect_signals_window_1h`) → agrégation → Claude via Bedrock → liste d’alertes JSON.

## Sur EC2 (Amazon Linux / même famille)

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

Tu peux aussi mettre `AWS_PROFILE=bao` dans un fichier `.env` à la racine du repo pour les scripts qui font `load_dotenv` (ex. tests), mais **`serve_app` ne lit pas `.env`** : pour uvicorn, exporte les variables dans le shell ou utilise systemd/docker avec `environment`.

**Sur EC2 avec rôle IAM sur l’instance** : ne définis pas `AWS_PROFILE` ; boto3 utilisera automatiquement les credentials du rôle.

Variables optionnelles pour l’API :

- `BEDROCK_MODEL_ID` — sinon défaut dans `bedrock_client.MODEL_ID_DEFAULT`
- `BEDROCK_MAX_TOKENS` — défaut `4096`

Voir `.env.example` à la racine du repo (sans secrets statiques).

### 3. Lancer l’API

```bash
cd ~/clair_obscur
export PYTHONPATH="$PWD/src"
python3 -m uvicorn backend.model.serve_app:app --host 0.0.0.0 --port 8080
```

Ou depuis n’importe où sous la racine du repo :

```bash
./src/backend/scripts/run_model_serve.sh
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

### 6. Docker (minimal)

À la racine du dépôt. Le conteneur utilise **`AWS_PROFILE`** + le dossier **`~/.aws`** monté en lecture seule (après `aws sso login` sur la machine hôte). Optionnel : `.env` avec `AWS_PROFILE`, `BEDROCK_*` (voir `.env.example`).

```bash
export AWS_PROFILE=bao   # ton profil SSO
./src/backend/scripts/run_model_docker.sh
```

API **+ worker SQS** (prédictions écrites dans `s3://model-attacks-predictions/predictions/` par défaut) : renseigne **`SQS_QUEUE_URL`** dans `.env`, puis :

```bash
./src/backend/scripts/run_model_docker.sh --profile sqs
```

Le worker tourne en boucle (**long polling** SQS, équivalent pratique à une tâche planifiée). Mode **`PREDICT_MODE=inline`** par défaut dans Compose : appelle **`predict_alerts`** sans passer par HTTP. Pour déléguer à l’API du même compose : `PREDICT_MODE=http` et `PREDICT_API_URL=http://model:8080`.

Arrêt : `docker compose -f docker-compose.model.yml down`.  
Arrière-plan : ajoute `-d` à la fin de la commande `docker compose`.

Sans le script :

```bash
docker compose -f docker-compose.model.yml up --build
docker compose --profile sqs -f docker-compose.model.yml up --build
```

Si la sous-commande `compose` n’existe pas sur ton EC2, installe le plugin Docker Compose ou utilise uniquement `docker build` / `docker run` (voir message d’erreur du script).

**Credentials :** avec Compose, **`~/.aws` est monté depuis l’hôte** (écriture nécessaire pour le cache SSO sous `~/.aws/sso/cache`) et **`AWS_PROFILE`** est repris de l’hôte. Sur une EC2 qui ne s’authentifie **que** par rôle IAM (sans `~/.aws`), adapte ou retire le volume dans `docker-compose.model.yml`.

Fais d’abord `aws sso login --profile …` sur la machine qui lance Docker, puis :

```bash
export AWS_PROFILE=bao
docker compose -f docker-compose.model.yml up --build
```

Sans Compose :

```bash
docker build -f src/backend/model/Dockerfile -t clair-model .
docker run --rm -p 8080:8080 -e AWS_REGION=eu-west-3 -e AWS_PROFILE=bao \
  -v ~/.aws:/root/.aws clair-model
```

## Fichiers utiles

| Fichier | Rôle |
|--------|------|
| `serve_app.py` | FastAPI `/health`, `/predict` |
| `predict.py` | `predict_alerts(events, …)` (profil AWS / chaîne boto3) |
| `requirements-api.txt` | Dépendances pour l’API |
| `Dockerfile` | Image avec uvicorn |
| `../../docker-compose.model.yml` | Compose : build + port 8080 + `.env` |
| `../../.dockerignore` | Contexte de build allégé |
| `../scripts/run_model_serve.sh` | Lance uvicorn avec `PYTHONPATH` correct |
| `../scripts/run_model_docker.sh` | Build + Compose (`--profile sqs` pour le worker) |
| `../scripts/sqs_predict_worker.py` | Worker SQS → S3 logs → prédictions → S3 JSON |

Le modèle `.env` versionné est à la racine du repo : `.env.example`.
