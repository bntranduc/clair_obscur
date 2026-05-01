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

### 2. Credentials AWS et variables

**Option A — Rôle IAM sur l’instance (recommandé)**  
Attache un rôle avec les permissions Bedrock nécessaires (`Converse` / modèle ou profil d’inférence). Tu n’as pas besoin de clés dans `.env` pour Bedrock ; définis au minimum la région :

```bash
export AWS_REGION=eu-west-3
export AWS_DEFAULT_REGION=eu-west-3
```

**Option B — Clés temporaires ou utilisateur IAM**  
Copie le modèle puis édite les valeurs (ne committe jamais `.env`) :

```bash
cp .env.example .env
nano .env
```

Renseigne au minimum :

- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_SESSION_TOKEN` (obligatoire pour les sessions STS / SSO / rôle assumé)
- `AWS_REGION` / `AWS_DEFAULT_REGION` (ex. `eu-west-3`)

Variables optionnelles pour l’API (`serve_app.py`) :

- `BEDROCK_MODEL_ID` — sinon défaut dans le code (`bedrock_client.MODEL_ID_DEFAULT`)
- `BEDROCK_MAX_TOKENS` — défaut `4096`

**Important :** `serve_app` ne charge pas automatiquement `.env`. Il faut exporter les variables dans le shell **avant** de lancer uvicorn :

```bash
set -a
source ./.env
set +a
```

(Vérifie que ton `.env` est au format `KEY=value`, une variable par ligne. Évite les espaces autour du `=`.)

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

**Credentials :** le conteneur ne récupère pas automatiquement le rôle IAM de l’instance. En pratique : remplis **`AWS_*` dans `.env`** (lu par Compose), ou monte un répertoire de credentials :

```bash
docker build -f src/backend/model/Dockerfile -t clair-model .
docker run --rm -p 8080:8080 -e AWS_REGION=eu-west-3 \
  -v ~/.aws:/root/.aws:ro clair-model
```

Sans Compose : `docker run --rm -p 8080:8080 --env-file .env clair-model` après le `docker build` ci-dessus.

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
