import os
import glob
from tokenizers import Tokenizer
from tokenizers.models import BPE
from tokenizers.trainers import BpeTrainer
from tokenizers.pre_tokenizers import ByteLevel
from tokenizers.decoders import ByteLevel as ByteLevelDecoder

SPECIAL_TOKENS = ["[LOGS]", "[EXPLANATION]"]


class LogTokenizer:
    def __init__(self, tokenizer: Tokenizer):
        self._tokenizer = tokenizer

    @property
    def vocab_size(self) -> int:
        return self._tokenizer.get_vocab_size()

    @property
    def special_tokens(self) -> dict:
        vocab = self._tokenizer.get_vocab()
        return {
            "LOGS": vocab["[LOGS]"],
            "EXPLANATION": vocab["[EXPLANATION]"],
        }

    def encode(self, text: str) -> list[int]:
        return self._tokenizer.encode(text).ids

    def decode(self, ids: list[int]) -> str:
        # ByteLevelDecoder strips special tokens, so we decode chunks of regular
        # tokens and splice special token strings back in manually.
        inv_vocab = {v: k for k, v in self._tokenizer.get_vocab().items()}
        special_ids = set(self.special_tokens.values())
        parts = []
        chunk: list[int] = []
        for id_ in ids:
            if id_ in special_ids:
                if chunk:
                    parts.append(self._tokenizer.decode(chunk))
                    chunk = []
                parts.append(inv_vocab[id_])
            else:
                chunk.append(id_)
        if chunk:
            parts.append(self._tokenizer.decode(chunk))
        return "".join(parts)

    def save(self, path: str) -> None:
        self._tokenizer.save(path)


def _collect_files(corpus_path: str) -> list[str]:
    if os.path.isfile(corpus_path):
        return [corpus_path]
    patterns = ["*.txt", "*.log"]
    files = []
    for pattern in patterns:
        files.extend(glob.glob(os.path.join(corpus_path, "**", pattern), recursive=True))
    return files


def _iter_lines(files: list[str]):
    for path in files:
        with open(path, encoding="utf-8", errors="replace") as f:
            yield from f


def train(corpus_path: str, vocab_size: int = 4096, save_path: str = "tokenizer.json") -> None:
    files = _collect_files(corpus_path)
    if not files:
        raise ValueError(f"No .txt or .log files found under {corpus_path!r}")

    tokenizer = Tokenizer(BPE(unk_token="[UNK]"))
    tokenizer.pre_tokenizer = ByteLevel(add_prefix_space=False)
    tokenizer.decoder = ByteLevelDecoder()

    trainer = BpeTrainer(
        vocab_size=vocab_size,
        special_tokens=["[UNK]"] + SPECIAL_TOKENS,
    )

    tokenizer.train_from_iterator(_iter_lines(files), trainer)
    tokenizer.save(save_path)


def load(path: str) -> LogTokenizer:
    tokenizer = Tokenizer.from_file(path)
    return LogTokenizer(tokenizer)
