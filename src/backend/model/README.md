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

À la racine du dépôt. Pour Bedrock : `cp .env.example .env` puis édite les variables AWS — le fichier est **optionnel** au démarrage du conteneur (sans `.env`, seuls `/health` et la région auront un sens tant que tu n’appelles pas `/predict`).

```bash
docker compose -f docker-compose.model.yml up --build
```

`-d` pour tourner en arrière-plan : `docker compose -f docker-compose.model.yml up --build -d`.

Arrêt : `docker compose -f docker-compose.model.yml down`.

**Credentials :** avec Compose, **`~/.aws` est monté en lecture seule** et **`AWS_PROFILE`** est repris de l’hôte (profil SSO). Sur une EC2 qui ne s’authentifie **que** par rôle IAM (sans `~/.aws`), adapte ou retire le volume dans `docker-compose.model.yml`.

Fais d’abord `aws sso login --profile …` sur la machine qui lance Docker, puis :

```bash
export AWS_PROFILE=bao
docker compose -f docker-compose.model.yml up --build
```

Sans Compose :

```bash
docker build -f src/backend/model/Dockerfile -t clair-model .
docker run --rm -p 8080:8080 -e AWS_REGION=eu-west-3 -e AWS_PROFILE=bao \
  -v ~/.aws:/root/.aws:ro clair-model
```

## Fichiers utiles

| Fichier | Rôle |
|--------|------|
| `serve_app.py` | FastAPI `/health`, `/predict` |
| `predict.py` | `predict_alerts(events, …)` (lib + creds optionnels) |
| `requirements-api.txt` | Dépendances pour l’API |
| `Dockerfile` | Image avec uvicorn |
| `../../docker-compose.model.yml` | Compose : build + port 8080 + `.env` |
| `../../.dockerignore` | Contexte de build allégé |
| `../scripts/run_model_serve.sh` | Lance uvicorn avec `PYTHONPATH` correct |

Le modèle `.env` versionné est à la racine du repo : `.env.example`.
