# Day 1 Notes — Tokens, Context, Cost

## Setup
- Repo initialized.
- `token_explorer.py` runs against three samples: English prose, Python code, Bengali prose.
- Tokenizer used: `tiktoken` `cl100k_base` (GPT-4 family). Claude uses a
  different tokenizer; counts differ in absolute terms but the relative
  pattern across languages and modalities is the same.

## Observation 1 — English is the cheap case
English prose lands around **___ chars/token** (fill in after running).
Common words like " the", " models", " are" are *whole tokens*, prefix
space included. The tokenizer was trained on a corpus where English
dominated, so BPE merges captured frequent English subwords aggressively.

**Implication:** every cost estimate, latency estimate, and context-budget
plan I read in English-language blog posts assumes this ratio. It does
not generalize.

## Observation 2 — Code costs more than it looks
Python code comes in at roughly **___ chars/token**, materially worse than
prose. Indentation, colons, parens, and dunders each tend to consume a
token. A 200-line Python file is not "short context" — it can be 2-3K
tokens on its own.

**Implication for week 2 onward:** when building a code-aware RAG system,
chunk size in tokens does not map cleanly to chunk size in lines. A
"500-token chunk" of code might be only ~30 lines. Embedding models also
behave differently on code; this is why CodeBERT / code-specific embedders
exist.

## Observation 3 — Bengali pays the multilingual tax
Bengali prose with roughly the same character count as the English sample
took **___ tokens** vs. English's **___**, a ratio of **___×**.
Chars/token collapsed to about **___**. Individual Bengali graphemes
appeared as separate tokens; the tokenizer never learned common Bengali
subwords because Bengali was underrepresented in its training corpus.

**Implications, concrete:**
1. **Cost:** a Dhaka user asking the same question pays roughly ___× the
   API cost of a US user. For a free-tier product this directly affects
   unit economics in this market.
2. **Context budget:** the effective context window in Bengali is roughly
   200K / ___ ≈ ___K "equivalent English tokens." Long-context tricks
   like dumping a whole book into the prompt do not work as advertised
   for Bengali users.
3. **Latency:** more output tokens = more wall-clock time. Bengali
   responses are slower at the same model setting, all else equal.
4. **Design move:** when I build the research assistant, I should
   consider a routing layer that detects language and adjusts: smaller
   chunks for Bengali retrieval, more aggressive summarization in memory,
   maybe a separate eval set in Bengali so I don't ship a system that
   silently degrades for half my users.

## Reading: "Lost in the Middle" (Liu et al., 2023)

Core finding: when relevant information is placed in the *middle* of a
long input context, model accuracy drops sharply versus placing it at
the *beginning* or *end*. The shape is a U-curve. Holds across model
families and across long-context-claimed models.

**Why I care:**
- It kills the "just stuff everything in context, the model has 200K
  tokens" instinct. Effective context ≠ advertised context.
- For RAG, it means ranking matters even after retrieval: the most
  relevant chunk should be placed at the end (just before the question)
  or at the very start, not buried in position 12 of 20.
- It motivates **reranking** (week 2) and **context compression** (week 4).
- It changes how I should write system prompts: critical instructions go
  at the start *and* get restated near the end, not buried in the middle
  of a 3000-token system prompt.

## Friday reflection placeholder
Things still fuzzy:
-
What broke:
-
What I want to dig into next:
-