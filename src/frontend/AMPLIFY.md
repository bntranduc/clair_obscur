# Déployer le frontend sur AWS Amplify (depuis zéro)

## 1. Prérequis

- Repo Git (GitHub) avec ce `amplify.yml` à la **racine** du dépôt `clair_obscur`.
- Une instance EC2 (ou autre) qui expose l’**API dashboard** FastAPI sur le port **8010** (HTTP), avec le security group ouvert vers Internet (ou vers Amplify si tu restreins plus tard).

## 2. Créer l’app Amplify

1. Console [AWS Amplify](https://console.aws.amazon.com/amplify/) → **Create new app** → hébergement seul (sans Amplify Gen2 backend obligatoire).
2. Connecter le **repository** et la **branche** (ex. `main`).
3. Build : laisser **Build image** par défaut ; Amplify utilisera `amplify.yml` à la racine.
4. **Rôle IAM** : accepter la création du rôle de service Amplify (build + hébergement compute).

## 3. Variables d’environnement (obligatoires)

Dans **Hosting → Environment variables** (pour la branche, ou « All branches ») :

| Variable | Valeur | Quand |
|----------|--------|--------|
| `NEXT_PUBLIC_DASHBOARD_API_PROXY` | `1` | Toujours en prod Amplify (HTTPS) pour éviter le mixed content vers `http://EC2:8010`. |
| `DASHBOARD_API_URL` | `http://ec2-…amazonaws.com:8010` | **Sans** slash final. Variable **serveur** : utilisée par la route `src/app/api/dashboard-proxy/...` (Next.js → EC2). |

Optionnel :

| Variable | Usage |
|----------|--------|
| `NEXT_PUBLIC_DASHBOARD_API_URL` | Uniquement si tu **ne** passes **pas** par le proxy (navigateur → EC2 direct) ; en prod HTTPS avec proxy, tu peux l’omettre. |

Après toute modification des variables **`NEXT_PUBLIC_*`** : lancer un **nouveau build** (redeploy).

## 4. CORS côté EC2

Le navigateur n’appelle plus l’EC2 directement pour les données : c’est le **serveur Next** (Amplify) qui appelle `DASHBOARD_API_URL`. Il faut quand même que l’API EC2 accepte les requêtes depuis cette origine si tu testes autrement ; pour le proxy, configure sur le conteneur dashboard :

- `DASHBOARD_CORS_ORIGINS` avec l’URL HTTPS de ton app Amplify (ex. `https://main.d1234abcd.amplifyapp.com`).

## 5. Build & URL

Pousser le commit sur la branche connectée → Amplify lance `npm ci` puis `npm run build` dans `src/frontend`.

À la fin du build, l’URL du type `https://main.<id>.amplifyapp.com` sert l’app ; tester **Logs S3**, **Alertes**, **Appeler le modèle**.

## 6. Dépannage

| Symptôme | Piste |
|----------|--------|
| Build échoue sur Node | Vérifier que `amplify.yml` utilise bien **Node 20** (`nvm install 20`). |
| Page 404 sur `/` | Vérifier que **artifacts.baseDirectory** est bien `src/frontend/.next` et que l’app est détectée comme Next SSR par Amplify. |
| « Failed to fetch » / mixed content | Activer **`NEXT_PUBLIC_DASHBOARD_API_PROXY=1`** + **`DASHBOARD_API_URL`**. |
| 502 sur `/api/dashboard-proxy/...` | `DASHBOARD_API_URL` vide ou EC2 injoignable depuis le réseau Amplify ; SG **8010**. |
