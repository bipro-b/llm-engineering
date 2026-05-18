# LLM Engineering Journey

An 8-week build toward a deployed, evaluated, multi-agent RAG system with
memory. One project, layered week by week. The goal isn't the artifact —
it's understanding *why* every layer exists.

## Project: research assistant agent
Ingests documents, answers questions with citations, remembers user
context across sessions, plans multi-step research, uses tools.

## Progress

### Week 1 — LLM internals & production FastAPI wrapper
- [x] **Day 1** — Tokens, context, cost. Built `token_explorer.py`,
      measured English vs. code vs. Bengali tokenization, read
      *Lost in the Middle*.
- [x] **Day 2** — Minimal FastAPI wrapper. Async `/chat` endpoint over
      `AsyncAnthropic`, Pydantic validation at the edges, settings via
      `pydantic-settings`, project structure (`routes/services/clients/schemas`),
      Dockerfile, smoke tests with dependency overrides.
- [ ] **Day 3** — Streaming (SSE), structured output, tool use
- [ ] **Day 4** — Retries, timeouts, token-usage logging, rate-limit handling
- [ ] **Day 5** — Deliberate failure modes: rate limits, token overflow,
      malformed JSON, dropped streams, runaway costs

### Weeks 2–8 (planned)
- [ ] **Week 2** — RAG that survives production: chunking, hybrid search,
      reranking, Ragas evaluation
- [ ] **Week 3** — Agents from first principles, then LangGraph
- [ ] **Week 4** — Context & memory engineering
- [ ] **Week 5** — Evaluation, observability, guardrails
- [ ] **Week 6** — System design, deployment, cost & latency
- [ ] **Weeks 7–8** — Multi-agent extension, design doc, interview prep

## Structure
```
week1/
  day1/
    token_explorer.py        # tokenization + cost explorer
    notes.md                 # observations + Lost in the Middle takeaways
  day2/
    app/
      main.py                # FastAPI app, lifespan, router mounting
      config.py              # pydantic-settings (single source of env truth)
      clients/anthropic.py   # AsyncAnthropic singleton
      routes/chat.py         # thin HTTP layer for /chat
      services/llm.py        # business logic, framework-agnostic
      schemas/chat.py        # request/response Pydantic models
    tests/
      conftest.py
      test_chat.py           # smoke tests with FakeLLM via dependency override
    Dockerfile               # multi-stage, non-root, healthcheck
    pyproject.toml
    .env.example
    README.md
  day3/ …
week2/ …
```

## Stack (planned, evolving)
- Python 3.11+, FastAPI, asyncio
- Anthropic SDK (primary), OpenAI SDK (comparison)
- Postgres + pgvector OR Qdrant — pick in week 2
- LangGraph for the agent layer (week 3)
- Langfuse for observability (week 5)
- Docker; cloud host TBD (week 6)

## Operating rules
- ~20 hours/week: 70% building, 20% reading, 10% reflecting.
- Push to GitHub daily, even when the code is bad.
- When something works, deliberately break it before moving on.
- Friday reflection note in `weekN/reflections.md`: what broke, what was learned, what's still fuzzy.