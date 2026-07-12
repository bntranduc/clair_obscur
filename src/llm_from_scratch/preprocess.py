"""The model's input contract: ID normalization and the pair template.

Everything the model ever sees — training pairs, tokenizer corpus, inference
prompts — goes through this module, so annotation (annotate.py) and inference
(generate.py) stay bit-identical. The dataset on disk and the 16k-mixed
tokenizer vocab were produced with exactly these regexes and this template.

The regexes are FROZEN — they define the model's input contract and must stay in sync with the training data. Known residual
gaps, all present in the training distribution and therefore NOT to be fixed
here (fixing them would recreate the train/inference skew this module
eliminates):

- False positives: all-letter hex-alphabet words >= 6 chars ("decade",
  "efface") and letter/digit mixes like "abc123" become <HEX>.
- False negatives: "0x"-prefixed hex ("0xDEADBEEF" — the "x" breaks the
  lookbehind), IPv6 shorthand ("fe80::dead:beef:1" — segments < 6 chars),
  and base62/mixed-case ids ("sk-Ab3xY9zQ12") pass through untouched.
"""

import re

# ID normalization — request IDs and other high-entropy identifiers are noise
# the model should not learn to predict, and they compress badly under a
# small BPE vocab. Replaced with placeholders before chunking.
# Order matters: most specific pattern first, so e.g. a UUID embedded right
# after "req-" is consumed whole by REQID_RE rather than left partially
# replaced by UUID_RE.
REQID_RE = re.compile(r"\breq-[0-9a-fA-F-]{6,}\b")
UUID_RE = re.compile(
    r"(?<![0-9a-fA-F])[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}(?![0-9a-fA-F])"
)
# Hex runs of >=6 chars that contain at least one a-f letter (a purely
# numeric run is handled by DECIMAL_RE instead, so the two placeholders
# stay meaningfully distinct).
HEXRUN_RE = re.compile(
    r"(?<![0-9a-zA-Z])(?=[0-9a-fA-F]*[a-fA-F])[0-9a-fA-F]{6,}(?![0-9a-zA-Z])"
)
DECIMAL_RE = re.compile(r"(?<![0-9a-zA-Z])\d{6,}(?![0-9a-zA-Z])")


def normalize_ids(text: str) -> str:
    """Replace high-entropy identifiers with placeholders.

    Order: req-<hex> first (most specific), then bare UUIDs, then generic
    hex runs, then decimal runs. Meant to run per log line, before chunking.
    """
    text = REQID_RE.sub("<REQID>", text)
    text = UUID_RE.sub("<UUID>", text)
    text = HEXRUN_RE.sub("<HEX>", text)
    text = DECIMAL_RE.sub("<NUM>", text)
    return text


def normalize_log_lines(text: str) -> list[str]:
    """Raw log text -> the exact lines the annotation pipeline feeds the model:
    blank lines dropped, IDs normalized line by line."""
    return [normalize_ids(l) for l in text.splitlines() if l.strip()]


def format_prompt(log_block: str) -> str:
    """The inference prompt: everything of a pair up to where the model's
    completion starts."""
    return f"[LOGS]\n{log_block}\n[EXPLANATION]\n"


def format_pair(log_block: str, explanation: str) -> str:
    return f"{format_prompt(log_block)}{explanation}\n"
