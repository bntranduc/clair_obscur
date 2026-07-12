"""Explain API: a minimal local FastAPI app wrapping generate.py's inference
path. `POST /explain` normalizes IDs, greedy-decodes the model, and truncates
oversized input to the tail rather than rejecting it. The model is loaded once
at startup, not per request.
"""

import os
from contextlib import asynccontextmanager

import torch
from fastapi import FastAPI
from pydantic import BaseModel

from generate import fit_prompt_to_budget, generate, load_checkpoint

DEFAULT_CHECKPOINT = "model_prod"
DEFAULT_TOKENIZER = "tokenizer.json"
# Greedy decoding, 200 tokens reserved for the explanation — the budget the
# training pairs were built around (see generate.py's own default).
MAX_NEW_TOKENS = 200

_state: dict = {}


def _load_state() -> dict:
    checkpoint_dir = os.environ.get("EXPLAIN_CHECKPOINT", DEFAULT_CHECKPOINT)
    tokenizer_path = os.environ.get("EXPLAIN_TOKENIZER", DEFAULT_TOKENIZER)
    device = torch.device("cpu")
    model, tokenizer, _ = load_checkpoint(checkpoint_dir, device, tokenizer_path=tokenizer_path)
    model = model.to(device)
    return {
        "model": model,
        "tokenizer": tokenizer,
        "device": device,
        "checkpoint": checkpoint_dir,
        "tokenizer_path": tokenizer_path,
        "params": sum(p.numel() for p in model.parameters()),
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    _state.update(_load_state())
    yield
    _state.clear()


app = FastAPI(lifespan=lifespan)


class ExplainRequest(BaseModel):
    logs: str


class ExplainResponse(BaseModel):
    explanation: str
    truncated: bool
    lines_used: int


@app.post("/explain", response_model=ExplainResponse)
def explain(payload: ExplainRequest) -> ExplainResponse:
    model = _state["model"]
    tokenizer = _state["tokenizer"]
    device = _state["device"]
    ctx_len = model.pos_emb.weight.shape[0]

    _, total_lines, dropped_lines = fit_prompt_to_budget(payload.logs, tokenizer, ctx_len, MAX_NEW_TOKENS)
    explanation = generate(
        model, tokenizer, payload.logs,
        max_new_tokens=MAX_NEW_TOKENS, temperature=0.0, device=device,
    )

    return ExplainResponse(
        explanation=explanation,
        truncated=dropped_lines > 0,
        lines_used=total_lines - dropped_lines,
    )


@app.get("/health")
def health() -> dict:
    return {
        "checkpoint": _state["checkpoint"],
        "params": _state["params"],
        "tokenizer": _state["tokenizer_path"],
    }
