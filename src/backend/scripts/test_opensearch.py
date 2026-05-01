"""
Test de connexion et d'ingestion OpenSearch.
Les droits de l'utilisateur 'etudiant' ne permettent pas les appels cluster
(_cat/indices, GET /), on va directement sur les endpoints d'index.

Ingestion temps réel type prod : producteurs → Kafka (MSK) → Spark → S3 ;
voir `backend.streaming_ingestion` (schéma JSON compatible `_source` / `timestamp`).
"""
import json
import os
import requests

OS_URL = os.getenv(
    "OPENSEARCH_URL",
    "https://search-hackathon-cnd-pytppy2betrf5qnoqporwcqqbm.eu-west-3.es.amazonaws.com",
)
AUTH = (
    os.getenv("OPENSEARCH_USER", "etudiant"),
    os.getenv("OPENSEARCH_PASSWORD", "HackathonCND2026!"),
)
INDEX = os.getenv("OPENSEARCH_INDEX", "logs-raw")

SEP = "-" * 60


def pp(obj):
    print(json.dumps(obj, indent=2, ensure_ascii=False))


# ── 1. Compter les documents disponibles ────────────────────────────────────
print(f"\n{SEP}")
print(f"[1] Nombre de documents dans {INDEX}")
r = requests.get(f"{OS_URL}/{INDEX}/_count", auth=AUTH)
print(f"    Status : {r.status_code}")
if r.status_code == 200:
    print(f"    Total  : {r.json().get('count', '?')}")
else:
    print("    Erreur :", r.text[:300])

# ── 2. Récupérer 1 document et afficher ses champs ──────────────────────────
print(f"\n{SEP}")
print("[2] Exemple de document (champs disponibles)")
r = requests.post(
    f"{OS_URL}/{INDEX}/_search",
    auth=AUTH,
    json={"query": {"match_all": {}}, "size": 1},
)
print(f"    Status : {r.status_code}")
if r.status_code == 200:
    hits = r.json().get("hits", {}).get("hits", [])
    if hits:
        source = hits[0]["_source"]
        print(f"    Index  : {hits[0]['_index']}")
        print(f"    Champs : {sorted(source.keys())}")
        print("\n    Document complet :")
        pp(source)
    else:
        print("    Aucun document trouvé.")
else:
    print("    Erreur :", r.text[:300])

# ── 3. Tester le scroll (même mécanique que le Producer Scala) ───────────────
print(f"\n{SEP}")
print("[3] Test du scroll API (1 page de 5 docs)")
r = requests.post(
    f"{OS_URL}/{INDEX}/_search?scroll=1m",
    auth=AUTH,
    json={"query": {"match_all": {}}, "size": 5},
)
print(f"    Status : {r.status_code}")
if r.status_code == 200:
    body     = r.json()
    scroll_id = body.get("_scroll_id")
    hits     = body.get("hits", {}).get("hits", [])
    total    = body.get("hits", {}).get("total", {}).get("value", "?")
    print(f"    Total disponible : {total}")
    print(f"    Docs reçus       : {len(hits)}")
    print(f"    Scroll ID        : {scroll_id[:30]}..." if scroll_id else "    Pas de scroll_id")

    # Nettoyer le contexte scroll
    if scroll_id:
        requests.delete(
            f"{OS_URL}/_search/scroll",
            auth=AUTH,
            json={"scroll_id": scroll_id},
        )
        print("    Contexte scroll nettoyé.")
else:
    print("    Erreur :", r.text[:300])

# ── 4. Recherche filtrée (exemple du sujet) ──────────────────────────────────
print(f"\n{SEP}")
print('[4] Recherche filtrée — event_type = "authentication"')
r = requests.post(
    f"{OS_URL}/{INDEX}/_search",
    auth=AUTH,
    json={"query": {"match": {"event_type": "authentication"}}, "size": 3},
)
print(f"    Status : {r.status_code}")
if r.status_code == 200:
    hits = r.json().get("hits", {}).get("hits", [])
    print(f"    Résultats : {len(hits)}")
    for h in hits:
        print(f"      → {h['_source']}")
else:
    print("    Erreur :", r.text[:300])

print(f"\n{SEP}\nTest terminé.\n")
