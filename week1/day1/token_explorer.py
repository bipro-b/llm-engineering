"""
token_explorer.py
=================
Day 1 of LLM Engineering Journey — feel the primitives.

What this script does:
  1. Takes one or more strings.
  2. For each, prints: character count, token count, the first N token IDs,
     the first N tokens decoded (so you can SEE how text fragments), the
     compression ratio (chars/token), and an estimated cost at current
     model prices.
  3. Compares English, code, and Bengali so you observe multilingual
     tokenization unfairness directly.

A note on tokenizers:
  - We use `tiktoken` with the `cl100k_base` encoding, which is what
    OpenAI's GPT-4 family uses. Claude uses a *different* tokenizer
    (Anthropic does not publish a local tokenizer; you'd hit their
    /v1/messages/count_tokens endpoint for exact counts).
  - The *shape* of what you observe (English compresses well, code is
    middling, Bengali is brutal) holds across all major tokenizers.
    Numbers differ; the lesson does not.
"""

from __future__ import annotations

import tiktoken
from dataclasses import dataclass


# Pricing per 1M tokens, in USD. UPDATE BEFORE SHIPPING ANYTHING REAL.
# Source: Anthropic pricing page (verify — these change).
PRICING = {
    "claude-haiku-4.5":  {"input": 1.00,  "output": 5.00},
    "claude-sonnet-4.5": {"input": 3.00,  "output": 15.00},
    "claude-opus-4":     {"input": 15.00, "output": 75.00},
    "gpt-4o":            {"input": 2.50,  "output": 10.00},
    "gpt-4o-mini":       {"input": 0.15,  "output": 0.60},
}


@dataclass
class TokenStats:
    """Holds the analysis result for one input string."""
    label: str
    text_preview: str
    char_count: int
    token_count: int
    first_ids: list[int]
    first_pieces: list[str]
    chars_per_token: float

    def estimated_input_cost(self, model: str) -> float:
        """Cost in USD if this text were sent AS INPUT to the given model."""
        if model not in PRICING:
            raise ValueError(f"unknown model {model}")
        return self.token_count / 1_000_000 * PRICING[model]["input"]


def analyze(text: str, label: str, encoder: tiktoken.Encoding,
            preview_n: int = 12) -> TokenStats:
    """Tokenize `text` and return a TokenStats object.

    preview_n: how many leading tokens to surface in the report. 12 is
    enough to see the pattern without flooding stdout.
    """
    ids = encoder.encode(text)
    # encoder.decode_single_token_bytes returns raw bytes; decode them
    # with errors='replace' so partial multibyte tokens (common with
    # non-Latin scripts) don't crash the print.
    pieces = [encoder.decode_single_token_bytes(i).decode("utf-8", errors="replace")
              for i in ids[:preview_n]]
    char_count = len(text)
    token_count = len(ids)
    return TokenStats(
        label=label,
        text_preview=(text[:60] + "…") if len(text) > 60 else text,
        char_count=char_count,
        token_count=token_count,
        first_ids=ids[:preview_n],
        first_pieces=pieces,
        chars_per_token=(char_count / token_count) if token_count else 0.0,
    )


def print_report(stats: TokenStats, model: str = "claude-sonnet-4.5") -> None:
    print(f"\n=== {stats.label} ===")
    print(f"preview         : {stats.text_preview!r}")
    print(f"characters      : {stats.char_count}")
    print(f"tokens          : {stats.token_count}")
    print(f"chars / token   : {stats.chars_per_token:.2f}")
    print(f"first token IDs : {stats.first_ids}")
    print(f"first pieces    : {stats.first_pieces}")
    cost = stats.estimated_input_cost(model)
    print(f"input cost @{model}: ${cost:.6f}")


# --- Three sample inputs ---------------------------------------------------
# 1. English prose: an excerpt about LLMs.
ENGLISH = (
    "Large language models are statistical engines that predict the next "
    "token given a sequence of prior tokens. They do not understand text in "
    "the way humans do; they have absorbed patterns so vast that the pattern "
    "completion looks like understanding. Whether that distinction matters "
    "depends on what you are trying to build."
)

# 2. Python code: deliberately includes indentation, dunders, operators.
CODE = '''\
def retrieve(query: str, k: int = 5) -> list[Document]:
    """Hybrid retrieval: dense + BM25, then RRF, then rerank."""
    dense_hits  = vector_store.similarity_search(query, k=k * 4)
    sparse_hits = bm25_index.search(query, k=k * 4)
    fused       = reciprocal_rank_fusion(dense_hits, sparse_hits)
    return reranker.rerank(query, fused)[:k]
'''

# 3. Bengali prose: same meaning as the English paragraph, roughly.
BENGALI = (
    "বৃহৎ ভাষা মডেলগুলি পরিসংখ্যানগত ইঞ্জিন যা পূর্ববর্তী টোকেনের ক্রম দেখে "
    "পরবর্তী টোকেন অনুমান করে। তারা মানুষের মতো করে পাঠ্য বোঝে না; তারা "
    "এত বিশাল প্যাটার্ন আত্মস্থ করেছে যে প্যাটার্ন পূরণ দেখতে বোঝার মতো লাগে। "
    "সেই পার্থক্যটা গুরুত্বপূর্ণ কি না তা নির্ভর করে আপনি কী তৈরি করতে চান তার ওপর।"
)


def main() -> None:
    enc = tiktoken.get_encoding("cl100k_base")
    samples = [
        ("English prose",  ENGLISH),
        ("Python code",    CODE),
        ("Bengali prose",  BENGALI),
    ]
    all_stats = [analyze(text, label, enc) for label, text in samples]
    for s in all_stats:
        print_report(s)

    # Side-by-side fairness comparison: cost of saying the same thing.
    print("\n=== Multilingual fairness check ===")
    print(f"{'language':<16}{'tokens':>8}{'chars/tok':>12}{'$ at sonnet':>16}")
    for s in all_stats:
        print(f"{s.label:<16}{s.token_count:>8}{s.chars_per_token:>12.2f}"
              f"{s.estimated_input_cost('claude-sonnet-4.5'):>16.6f}")


if __name__ == "__main__":
    main()