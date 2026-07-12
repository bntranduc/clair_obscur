# local-log-llm — dossier de rendu

Un petit modèle de langage (**~34M de paramètres, entraîné from scratch en
PyTorch sur un laptop**) qui lit un bloc de logs système et explique en anglais
simple ce qui se passe, avec une action recommandée. Il tourne entièrement en
local : les logs ne quittent jamais la machine.

Ce dossier contient **le minimum pour faire tourner l'API** (code d'inférence +
modèle + tokenizer + Dockerfile) et **le rapport du comparatif** contre Claude
Sonnet 5 (`rapport/`).

## Lancer l'API

### Avec Docker (recommandé)

```bash
docker build -t log-explain-api .
docker run --rm -p 8000:8000 log-explain-api

curl -s localhost:8000/health
curl -s -X POST localhost:8000/explain -H 'content-type: application/json' \
  -d '{"logs": "kernel: Out of memory: Kill process 1234 (java)"}'
# → {"explanation": "...", "truncated": false, "lines_used": 1}
```

### Sans Docker

```bash
python -m venv .venv && source .venv/bin/activate
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
uvicorn api:app --port 8000
```

**Contrat** : `POST /explain {"logs": "..."}` →
`{"explanation", "truncated", "lines_used"}`. Si l'entrée dépasse le contexte
du modèle (512 tokens), l'API garde **la fin** des logs (l'info actionnable est
dans la queue) et le signale via `truncated` — jamais d'erreur.

## Comment le modèle a été fabriqué (en 6 étapes)

Tout a été entraîné sur **une RTX 4070 Laptop (8 Go)**. Aucun poids pré-entraîné
externe : le modèle, le tokenizer et les données d'entraînement sont fabriqués
maison.

**1. Fabriquer les données.** Des logs publics réels
([Loghub](https://github.com/logpai/loghub) : Linux, OpenSSH, Hadoop,
OpenStack…) découpés en blocs et envoyés à Claude, qui rédige pour chacun une
explication + action. Résultat : **~6 500 paires** `[LOGS] → [EXPLANATION]`.
Les identifiants à haute entropie (UUID, hex, request-ids) sont remplacés par
des placeholders `<UUID>`/`<HEX>`/`<NUM>` — du bruit impossible à prédire, qui
compresse très mal. Split train/val gelé.

**2. Un tokenizer maison.** BPE 16 384 tokens, entraîné sur un mix texte
général + logs normalisés. Le premier essai (vocab 4096) tokenisait les logs si
cher que l'explication ne tenait plus dans le contexte — mesuré, diagnostiqué,
retrainé.

**3. Un GPT from scratch, en deux étages.** Architecture decoder-only classique
(`model.py`). D'abord un **pretrain** sur du texte général streamé (80 %
FineWeb, 20 % The Stack) pour apprendre l'anglais et la syntaxe technique ;
puis un **fine-tune** sur les paires de logs. Sans le pretrain, le modèle ne
converge pas : impossible d'apprendre l'anglais ET les logs sur 6 500 exemples.

**4. Choisir la taille par la mesure.** Un sweep automatique a entraîné
4 tailles (24M → 94M) **à budget GPU égal** (~24 h) : probes de learning rate,
pretrain court, fine-tune standardisé, classement à la val loss. Verdict en U :
le petit sature, le gros est affamé à temps égal — **M1 (8 couches / 8 têtes /
dim 512, ~34M) gagne**.

**5. Fine-tune final, avec ablation.** Deux fine-tunes depuis le même
pretrain : loss sur toute la séquence vs **loss sur l'explication seule** (le
modèle n'est plus entraîné à prédire les logs, seulement à les expliquer —
pari anti-hallucination), plus un vrai EOS appris. Le masquage gagne : val loss
**1.787** contre 1.886 (loss pleine) et 2.045 (recette de référence du sweep).
C'est ce checkpoint qui est embarqué ici.

**6. Se comparer honnêtement.** Comparatif contre **Claude Sonnet 5** sur 16
blocs de logs jamais vus, jugés **en aveugle** (réponses anonymisées et
mélangées) — plus les axes mesurés : coût, latence, empreinte, confidentialité.
Résultat complet dans `rapport/report.md`. En bref : Sonnet gagne la qualité
16/16 (attendu face à un modèle frontier) ; le local attrape l'essentiel du
diagnostic mais invente des détails ; en échange il coûte ~0 $, répond en
1,1 s sur GPU local, fonctionne offline et garde les logs privés.

## Contenu du dossier

```
api.py                    — l'API HTTP (FastAPI) : POST /explain, GET /health
generate.py               — décodage greedy, stop EOS, troncature au budget
model.py                  — le GPT (from scratch, PyTorch)
preprocess.py             — normalisation des IDs (contrat d'entrée du modèle)
tokenizer.py              — chargement du BPE
tokenizer.json            — tokenizer BPE 16k entraîné maison
checkpoint/ckpt.pt        — le modèle final (~34M params, poids seuls, 135 Mo)
Dockerfile                — image CPU autonome
rapport/report.md         — comparatif vs Claude Sonnet 5 (protocole + résultats)
rapport/blind_pack.md     — les 16 duels anonymisés annotés par le juge aveugle
rapport/*_outputs.json    — sorties brutes des deux systèmes (avec latences)
```
