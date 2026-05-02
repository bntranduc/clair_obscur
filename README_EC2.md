# EC2 — remise en marche rapide

Guide pour rétablir **API modèle** (`/predict`, Bedrock) et **worker SQS** quand SSO, Docker ou les permissions cassent. Toutes les commandes supposent que tu es connecté en **`ec2-user`** et que le dépôt est à jour (`git pull`).

---

## Check-list express

| Problème | Action |
|----------|--------|
| `Token has expired and refresh failed` (502 sur `/predict`) | Sur l’EC2 : SSO ci-dessous, puis **`docker compose … restart model`** (et **`worker`** si besoin). |
| `[Errno 13] Permission denied` sur `~/.aws/sso/cache/...` | **`sudo chown -R ec2-user:ec2-user ~/.aws`** puis **`chmod -R u+rwX ~/.aws`**, puis SSO. |
| Navigateur : `127.0.0.1 refused` pendant `aws sso login` | Tu as ouvert une URL avec **`redirect_uri=127.0.0.1`** depuis une machine qui n’est pas celle où tourne la CLI. Utilise **`--use-device-code`** sur l’EC2 (voir § SSO). |
| Le conteneur ne voit pas le bon profil | Vérifie **`.env`** à la racine du repo : **`AWS_PROFILE=<même nom que ton profil CLI>`**. Redémarre les services. |

---

## 1. SSO sur EC2 (sans navigateur sur le serveur)

```bash
aws sso login --profile <TON_PROFIL> --use-device-code
```

Ouvre l’URL affichée (**AWS access portal / device**) sur **ton téléphone ou ton PC**, entre le **code utilisateur**. Ne compte pas sur une redirection vers `localhost` sur le serveur sans tunnel SSH.

Vérifier que la CLI voit bien le compte :

```bash
aws sts get-caller-identity --profile <TON_PROFIL>
```

---

## 2. Permissions sur `~/.aws` (souvent après Docker)

Les conteneurs montent **`~/.aws`**. Si des fichiers ont été créés en **root**, **`ec2-user`** ne peut plus écrire le cache SSO :

```bash
sudo chown -R ec2-user:ec2-user /home/ec2-user/.aws
chmod -R u+rwX /home/ec2-user/.aws
```

---

## 3. Variables et Compose

À la **racine du repo** (là où se trouve **`docker-compose.model.yml`** et **`.env`** ) :

- **`AWS_PROFILE`** = nom du profil avec lequel tu fais **`aws sso login`**
- **`AWS_REGION`** / **`AWS_DEFAULT_REGION`** = ex. **`eu-west-3`**

API seule :

```bash
cd ~/clair_obscur   # adapte le chemin
docker compose -f docker-compose.model.yml up --build -d
```

API + worker SQS (après avoir défini **`SQS_QUEUE_URL`** dans **`.env`** ou l’environnement) :

```bash
docker compose --profile sqs -f docker-compose.model.yml up --build -d
```

Ou avec le script :

```bash
./src/backend/scripts/run_model_docker.sh --profile sqs -d
```

Après un **nouveau login SSO**, redémarrer pour repartir propre :

```bash
docker compose -f docker-compose.model.yml restart model
# avec worker :
docker compose --profile sqs -f docker-compose.model.yml restart model worker
```

---

## 4. Tests rapides (sur l’EC2)

Santé :

```bash
curl -sS http://127.0.0.1:8080/health
```

Prédiction minimale :

```bash
curl -sS -X POST "http://127.0.0.1:8080/predict" \
  -H "Content-Type: application/json" \
  -d '{"events":[{"timestamp":"2026-01-15T08:00:01Z","log_source":"authentication","source_ip":"203.0.113.50","auth_method":"ssh","status":"failure","username":"root"},{"timestamp":"2026-01-15T08:00:02Z","log_source":"authentication","source_ip":"203.0.113.50","auth_method":"ssh","status":"failure","username":"u2"},{"timestamp":"2026-01-15T08:00:03Z","log_source":"authentication","source_ip":"203.0.113.50","auth_method":"ssh","status":"failure","username":"u3"},{"timestamp":"2026-01-15T08:00:04Z","log_source":"authentication","source_ip":"203.0.113.50","auth_method":"ssh","status":"failure","username":"u4"},{"timestamp":"2026-01-15T08:00:05Z","log_source":"authentication","source_ip":"203.0.113.50","auth_method":"ssh","status":"failure","username":"u5"}]}'
```

Depuis **ton PC** vers l’instance publique : remplace **`127.0.0.1`** par l’**IP ou DNS** de l’EC2 ; ouvre le **security group** sur le port **8080** si besoin.

---

## 5. Logs Docker

```bash
docker compose -f docker-compose.model.yml logs -f model
```

---

## 6. Sécurité (rappel)

- Ne colle **jamais** dans un chat ou un ticket les **exports temporaires** (access key / secret / session token) de la console IAM Identity Center : considère-les **révoquées** si elles ont fuité et régénère-en via SSO ou la console.
- Pour une charge **production** sur EC2, préfère un **rôle IAM d’instance** avec droits Bedrock (et retire la dépendance au montage **`~/.aws`** SSO si ton organisation le permet).

---

## API logs S3 (frontend)

Port **8020** par défaut : **`./scripts/run_api.sh`** (`PYTHONPATH=src`, **`AWS_PROFILE`** lu depuis l’environnement ou **`.env`** si tu exportes les variables avant). Next.js proxifie **`/bff-api`** → **`FRONTEND_API_PROXY_TARGET`** (voir **`.env.example`**).

## Référence détaillée

Installation, variables Bedrock, Docker : **`src/backend/model/README.md`**.
