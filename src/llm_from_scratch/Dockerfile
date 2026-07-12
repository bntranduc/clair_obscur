# Explain API — image CPU autonome (modèle ~34M embarqué).
#
#   docker build -t log-explain-api .
#   docker run --rm -p 8000:8000 log-explain-api
#   curl -s localhost:8000/health
#   curl -s -X POST localhost:8000/explain -H 'content-type: application/json' \
#       -d '{"logs": "kernel: Out of memory: Kill process 1234"}'

FROM python:3.11-slim

WORKDIR /app

# Torch CPU uniquement — l'image ne sert que l'inférence d'un modèle ~34M.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir fastapi uvicorn tokenizers

COPY model.py preprocess.py tokenizer.py generate.py api.py ./
COPY tokenizer.json ./tokenizer.json
COPY model_prod ./model_prod

EXPOSE 8000

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
