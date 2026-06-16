import os
import time
import uuid
from contextlib import asynccontextmanager

import torch
from fastapi import FastAPI
from pydantic import BaseModel

from generate import generate as generate_text, load_checkpoint

CHECKPOINT_DIR = os.environ.get("CHECKPOINT_DIR", "checkpoints/finetune-04/step-10000")

_model = None
_tok = None
_device = torch.device("cpu")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _model, _tok
    _model, _tok, _ = load_checkpoint(CHECKPOINT_DIR, _device)
    _model = _model.to(_device)
    yield


app = FastAPI(lifespan=lifespan)


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    model: str = "log-llm"
    messages: list[Message]
    max_tokens: int = 200
    temperature: float = 0.8
    top_p: float = 0.9


@app.post("/v1/chat/completions")
def chat_completions(req: ChatRequest):
    log_text = ""
    for msg in reversed(req.messages):
        if msg.role == "user":
            log_text = msg.content
            break

    result = generate_text(
        _model, _tok, log_text,
        max_new_tokens=req.max_tokens,
        temperature=req.temperature,
        top_p=req.top_p,
        device=_device,
    )

    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": "log-llm",
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": result},
            "finish_reason": "stop",
        }],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }
