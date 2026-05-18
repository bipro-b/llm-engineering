# Week 1 · Day 2 — Minimal FastAPI Wrapper (Gemini)

A single-endpoint async service over Google's Gemini API. The structure is
deliberately larger than this endpoint needs because weeks 3–8 will reuse it.

## Layout

```
app/
  main.py             # FastAPI app + lifespan + router mounting
  config.py           # pydantic-settings, the single source of env truth
  schemas/chat.py     # request/response models (edge contracts)
  routes/chat.py      # HTTP-only layer, thin
  services/llm.py     # business logic, provider-agnostic
  clients/
    base.py           # LLMProvider Protocol — the abstraction
    gemini.py         # Gemini adapter that implements LLMProvider
```

## Run locally

```bash
# 1. Set up the env (Windows / Git Bash)
uv venv && source .venv/Scripts/activate   # or: python -m venv .venv && source .venv/Scripts/activate
uv pip install -e ".[dev]"                 # or: pip install -e ".[dev]"

# 2. Configure
cp .env.example .env
# edit .env: paste your GEMINI_API_KEY from https://aistudio.google.com/apikey

# 3. Run
python -m uvicorn app.main:app --reload --port 8000
```

Open `http://localhost:8000/docs` for the auto-generated OpenAPI UI.

## Smoke tests (no API key needed)

```bash
python -m pytest -q
```

## Manual checks

Health:
```bash
curl -s http://localhost:8000/health
```

Chat:
```bash
curl -s http://localhost:8000/chat \
  -H 'content-type: application/json' \
  -d '{
        "messages":[{"role":"user","content":"In one sentence, what is a token?"}],
        "temperature": 0.2,
        "max_tokens": 200
      }'
```

Validation failure (422 with field-level errors):
```bash
curl -s http://localhost:8000/chat \
  -H 'content-type: application/json' \
  -d '{"messages":[{"role":"user","content":"hi"}],"temperature": 9}'
```

## Architecture note — why this was easy to swap

Yesterday `LLMService` depended on `AsyncAnthropic`. Today it depends on
`LLMProvider` — a Protocol defined in `clients/base.py`. The Gemini SDK
quirks (different roles, different field names, different response shape)
are all contained in `clients/gemini.py`. Nothing in `routes/`, `schemas/`,
or `services/` had to change to support its underlying logic.

Adding another provider (Anthropic, OpenAI, Groq) means: new file in
`clients/`, change one import in `routes/chat.py`. That's the dependency
inversion principle paying for itself.

## What's intentionally NOT here yet

- Streaming (day 3)
- Structured output / tool use (day 3)
- Retries with exponential backoff + jitter (day 4)
- Token-usage logging to a database (day 4)
- Rate-limit handling (day 4)