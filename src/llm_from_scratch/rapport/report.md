# Comparatif — modèle local M1 (34M) vs Claude Sonnet 5

Comparaison multi-axes honnête : qualité jugée en aveugle sur des blocs de logs
jamais vus, plus les axes mesurés (coût, latence, empreinte, confidentialité).

## Systèmes comparés

| | Local | Claude Sonnet 5 |
|---|---|---|
| Modèle | M1 — GPT from scratch, 8 couches / 8 têtes / dim 512, **33,8M params mesurés**, contexte 512, tokenizer BPE 16k maison | `claude-sonnet-5` (frontier, taille non publiée), API Messages directe |
| Entraînement | Pretrain ~729M tokens (FineWeb + The Stack) + fine-tune 12k steps sur 5 812 paires (log, explication) annotées | — |
| Décodage | Greedy, arrêt EOS, max 200 tokens | Défauts API (thinking adaptatif), max 600 tokens |
| Checkpoint | Fine-tune « loss explication seule », meilleur checkpoint de validation | — |

## Protocole qualité

- **Entrées** : 16 blocs de logs bruts held-out (1 par source : Linux, OpenSSH,
  Hadoop, OpenStack, Windows…), jamais vus à l'entraînement, **normalisés à
  l'identique** pour les deux systèmes (placeholders `<UUID>`/`<HEX>`/`<NUM>`).
- **Consigne Sonnet** : rôle « assistant d'analyse de logs », résumé + action
  recommandée, interdiction d'inventer des détails. Zero-shot.
- **Juge** : **Claude Opus, en aveugle** — le juge n'a eu accès qu'au paquet
  anonymisé (`blind_pack.md` : réponses A/B mélangées aléatoirement par bloc),
  jamais à la clé d'anonymisation ni aux sorties nommées. Grille par bloc :
  gist correct ? faits inventés (détails absents des logs, comptés un à un) ?
  action utile ? verdict A/B/égalité. **Caveat assumé** : Opus ne concourt pas,
  mais c'est un modèle Anthropic qui arbitre un duel impliquant Sonnet — moins
  solide qu'un juge humain, plus solide que Sonnet s'auto-jugeant.

## Résultats qualité (16 blocs, jugement aveugle)

**Sonnet 5 gagne 16/16.** Le détail par système (agrégé depuis `blind_pack.md`
croisé avec la clé d'anonymisation) :

| Métrique | Local M1 | Sonnet 5 |
|---|---|---|
| Gist correct (sur 16) | 0 (8 « partiel », 8 « non ») | **16** |
| Faits inventés (total) | 40 (~2,5/bloc : PIDs, IPs, heures, services) | **0** |
| Action utile (sur 16) | 4 | 14 (2 absentes — les 2 réponses tronquées au plafond de 600 tokens) |
| Verdicts gagnés | 0 | **16** (aucune égalité) |

Modes d'échec du modèle local relevés par le juge : il identifie souvent la
famille d'événement (brute-force SSH, OOM, activité routinière) mais **invente
les détails** — mauvais PIDs/heures, services fantômes (« ftpd », « ARPT »), et
dans un cas une **action activement nuisible** (openssh : mauvaise IP à
bloquer). Ses meilleures sorties restent « partiel » : le gist sans la
fiabilité factuelle.

La validation interne raconte la même histoire : entraîner la loss sur
l'explication seule a amélioré la métrique (1.787 contre 1.886 pour la loss
pleine et 2.045 pour la recette de référence), mais à ce budget de pretrain
(~729M tokens, ~18 tokens/param) les détails factuels ne sont pas fiables.

## Axes mesurés (hors qualité)

Mesures réelles sur les 16 appels/générations du protocole.

| Axe | Local M1 | Claude Sonnet 5 |
|---|---|---|
| Latence médiane / bloc | **1,1 s** (RTX 4070 Laptop, greedy ≤200 tokens ; ~14,5 s en CPU conteneur Docker) | **6,0 s** (min 2,5 / max 8,1, API + thinking adaptatif) |
| Coût / 1 000 requêtes | **~0 $** (électricité locale, négligeable) | **7,77 $** au tarif liste 3 $/15 $ par MTok (5,18 $ au tarif de lancement) — mesuré : ~468 tokens in / ~424 out par requête |
| Empreinte | 33,8M params, 135 Mo sur disque, tourne sur un laptop 8 Go, **offline** | Frontier hébergé, connexion requise |
| Confidentialité | **Les logs ne quittent jamais la machine** | Logs envoyés à un service tiers |
| Verbosité | Concise (≤ 200 tokens) | ~424 tokens moyens, markdown structuré ; 2/16 réponses tapent le plafond de 600 |

## Lecture honnête

- Sonnet 5 gagne le duel qualité **16/16** — attendu face à un modèle frontier ;
  la mesure dit *comment* : le 34M local attrape le gist (8/16 « partiel »)
  mais n'est jamais fiable sur les détails. À ce stade il démontre le pipeline,
  pas un produit fini.
- L'échantillon fait 16 blocs : ordres de grandeur et modes d'échec, pas de
  pourcentages fins.
- Ce que le local achète en échange : **5× moins de latence** (1,1 s vs 6,0 s),
  **coût marginal ~nul** (vs ~7,8 $/1k requêtes), fonctionne **offline** et les
  logs **ne quittent pas la machine**.
- Levier n°1 identifié pour combler l'écart : le **budget de pretrain** — le
  modèle livré a vu ~18 tokens/param, là où la cible dimensionnée était
  200-270 tokens/param (pretrain long sacrifié à la deadline). Le sweep de
  tailles et l'ablation de fine-tune montrent que l'architecture et la recette
  sont déjà au bon endroit ; c'est le compute qui manque.
- Vu l'écart (16/16, 40 faits inventés contre 0), le sens du verdict ne dépend
  pas du choix du juge.

## Annexes

- `blind_pack.md` — les 16 duels anonymisés, annotés par le juge.
- `local_outputs.json`, `sonnet_outputs.json` — sorties brutes et latences.
