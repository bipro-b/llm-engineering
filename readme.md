# LLM Engineering Journey

An 8-week build toward a deployed, evaluated, multi-agent RAG system with
memory. One project, layered week by week. The goal isn't the artifact —
it's understanding *why* every layer exists.

## Project: research assistant agent
Ingests documents, answers questions with citations, remembers user
context across sessions, plans multi-step research, uses tools.

## Progress
- [x] Week 1 Day 1 — Tokens, context, cost
- [ ] Week 1 Day 2 —
- [ ] Week 1 Day 3 —
- [ ] Week 1 Day 4 —
- [ ] Week 1 Day 5 —
- [ ] …

## Structure
```
week1/
  day1/
    token_explorer.py
    notes.md
  day2/
  …
week2/
…
```

## Stack (planned, evolving)
- Python 3.11, FastAPI, asyncio
- Anthropic SDK (primary), OpenAI SDK (comparison)
- Postgres + pgvector OR Qdrant — pick in week 2
- LangGraph for the agent layer (week 3)
- Langfuse for observability (week 5)
- Docker, a cloud host TBD (week 6)