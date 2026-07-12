import argparse
import sys
from pathlib import Path

import torch

from model import GPT, GPTConfig
from preprocess import format_prompt, normalize_log_lines
from tokenizer import load as load_tokenizer


def load_checkpoint(ckpt_dir: str, device: torch.device, tokenizer_path: str | None = None):
    """Load a checkpoint. `tokenizer_path`, if given, overrides the tokenizer
    path embedded in the checkpoint at save time (used by the Explain API,
    to serve a tokenizer configured independently of the checkpoint
    via EXPLAIN_TOKENIZER)."""
    ckpt = torch.load(Path(ckpt_dir) / "ckpt.pt", map_location=device, weights_only=False)
    tok = load_tokenizer(tokenizer_path or ckpt["tokenizer_path"])
    cfg = ckpt["config"]
    model = GPT(GPTConfig(
        n_layer=cfg["n_layer"],
        n_head=cfg["n_head"],
        n_embd=cfg["n_embd"],
        ctx_len=cfg["ctx_len"],
        vocab_size=tok.vocab_size,
    ))
    model.load_state_dict(ckpt["model"])
    model.eval()
    return model, tok, cfg


def fit_prompt_to_budget(
    log_text: str, tokenizer, ctx_len: int, max_new_tokens: int
) -> tuple[list[int], int, int]:
    """Tail-truncation policy shared by the CLI (build_prompt_ids) and the
    Explain API: normalize the log text exactly like training
    data, then, if the tokenized prompt exceeds ctx_len - max_new_tokens,
    drop whole lines from the HEAD until it fits — the interesting part of a
    log lives in its tail. Returns (prompt_ids, total_lines, dropped_lines)
    so callers can report what happened instead of just warning about it.
    """
    lines = normalize_log_lines(log_text)
    budget = ctx_len - max_new_tokens
    total = len(lines)
    prompt_ids = tokenizer.encode(format_prompt("\n".join(lines)))
    dropped = 0
    while len(prompt_ids) > budget and lines:
        lines.pop(0)
        dropped += 1
        prompt_ids = tokenizer.encode(format_prompt("\n".join(lines)))
    return prompt_ids, total, dropped


def build_prompt_ids(
    log_text: str, tokenizer, ctx_len: int, max_new_tokens: int
) -> list[int]:
    """Tokenized prompt for raw log text, normalized exactly like training data.

    The whole pair must fit the context window, as it did at training time
    (annotate.py rejects pairs longer than ctx_len), so the prompt budget is
    ctx_len - max_new_tokens. Oversized input is truncated from the HEAD, at
    line boundaries — the interesting part of a log lives in its tail — with
    a stderr warning, never a refusal.
    """
    prompt_ids, total, dropped = fit_prompt_to_budget(log_text, tokenizer, ctx_len, max_new_tokens)
    if dropped:
        print(
            f"warning: dropped {dropped}/{total} log lines to fit context",
            file=sys.stderr,
        )
    return prompt_ids


@torch.no_grad()
def generate(
    model: GPT,
    tokenizer,
    log_text: str,
    max_new_tokens: int = 200,
    temperature: float = 0.8,
    top_k: int = 0,
    top_p: float = 0.9,
    repetition_penalty: float = 1.3,
    device: torch.device = torch.device("cpu"),
) -> str:
    ctx_len = model.pos_emb.weight.shape[0]
    prompt_ids = build_prompt_ids(log_text, tokenizer, ctx_len, max_new_tokens)
    explanation_start = len(prompt_ids)

    ids = torch.tensor([prompt_ids], dtype=torch.long, device=device)

    for _ in range(max_new_tokens):
        ids_cond = ids[:, -ctx_len:]
        logits = model(ids_cond)
        next_logits = logits[:, -1, :].clone()

        # temperature == 0 means greedy: skip scaling (dividing by zero would
        # blow up the logits before the argmax branch below).
        if temperature > 0 and temperature != 1.0:
            next_logits = next_logits / temperature

        # Penalise tokens already generated (not the prompt)
        if repetition_penalty != 1.0:
            for token_id in set(ids[0, explanation_start:].tolist()):
                if next_logits[0, token_id] > 0:
                    next_logits[0, token_id] /= repetition_penalty
                else:
                    next_logits[0, token_id] *= repetition_penalty

        if top_k > 0:
            topk_vals, _ = torch.topk(next_logits, top_k)
            next_logits = next_logits.masked_fill(next_logits < topk_vals[:, -1:], float("-inf"))

        if top_p < 1.0:
            sorted_logits, sorted_indices = torch.sort(next_logits, descending=True, dim=-1)
            sorted_probs = torch.softmax(sorted_logits, dim=-1)
            cumulative_probs = torch.cumsum(sorted_probs, dim=-1)
            sorted_logits = sorted_logits.masked_fill(cumulative_probs - sorted_probs > top_p, float("-inf"))
            next_logits = torch.zeros_like(next_logits).scatter_(1, sorted_indices, sorted_logits)

        if temperature > 0:
            probs = torch.softmax(next_logits, dim=-1)
            next_id = torch.multinomial(probs, num_samples=1)
        else:
            next_id = next_logits.argmax(dim=-1, keepdim=True)

        # Training pairs are padded with token 0 ([UNK]) after the explanation,
        # with unmasked loss, so the model is trained to emit 0 as a de-facto
        # EOS. The byte-level BPE never produces 0 organically, so this is
        # unambiguous. Stop here, before appending, so 0 never reaches the
        # decoded output.
        if next_id.item() == 0:
            break

        ids = torch.cat([ids, next_id], dim=1)

    return tokenizer.decode(ids[0, explanation_start:].tolist())


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a log explanation from a trained checkpoint.")
    parser.add_argument("--checkpoint", required=True, metavar="DIR", help="Checkpoint directory (contains ckpt.pt).")
    parser.add_argument("--logs", default=None, metavar="FILE", help="Path to log file. Reads from stdin if omitted.")
    parser.add_argument("--max-new-tokens", type=int, default=200, help="Max tokens to generate (default: 200).")
    parser.add_argument("--temperature", type=float, default=0.8, help="Sampling temperature (default: 0.8).")
    parser.add_argument("--top-k", type=int, default=0, help="Top-k sampling, 0 = disabled (default: 0).")
    parser.add_argument("--top-p", type=float, default=0.9, help="Nucleus sampling threshold (default: 0.9).")
    parser.add_argument("--repetition-penalty", type=float, default=1.3, help="Repetition penalty on generated tokens (default: 1.3).")
    args = parser.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model, tok, _ = load_checkpoint(args.checkpoint, device)
    model = model.to(device)

    log_text = Path(args.logs).read_text() if args.logs else sys.stdin.read()
    explanation = generate(
        model, tok, log_text,
        max_new_tokens=args.max_new_tokens,
        temperature=args.temperature,
        top_k=args.top_k,
        top_p=args.top_p,
        repetition_penalty=args.repetition_penalty,
        device=device,
    )
    print(explanation)


if __name__ == "__main__":
    main()
