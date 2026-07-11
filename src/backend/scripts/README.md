# Scripts backend

Scripts de maintenance et pipeline — à lancer avec `PYTHONPATH=src` depuis la racine du dépôt.

| Fichier | Description |
|---------|-------------|
| `run_ingestion_to_alerts.py` | Ingère un répertoire JSONL, exécute règles + LLM, écrit `database/alerts.json` |
| `run_local_pipeline.py` | Pipeline sur un seul fichier (debug) |
| `put_logs_from_s3_to_dynamo_db.py` | Import S3 → table DynamoDB `normalized-logs` |
| `sqs_predict_worker.py` | Alias CLI vers `python -m backend.worker` |
| `run_model_serve.sh` | Démarre `api.model_app` sur le port 8080 |
