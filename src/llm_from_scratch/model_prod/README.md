# Checkpoint prod (~130 Mo) — non versionné.

Copier le meilleur checkpoint ici :

```bash
cp checkpoint/ckpt.pt model_prod/ckpt.pt
```

En production EC2, le fichier est téléchargé depuis S3 (`LOG_LLM_MODEL_S3_URI`) via `scripts/ec2-sync-log-llm-model.sh`.

Upload initial depuis la machine de dev :

```bash
bash scripts/upload-log-llm-model.sh
```
