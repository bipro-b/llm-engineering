"""
Application entrypoint.

Run:  uvicorn app.main:app --reload
Test: curl -s localhost:8000/extract -H 'content-type: application/json' \
        -d '{"text":"Reach Dr. Amina Rahman, CTO at Bengal Robotics, amina@bengalrobotics.bd"}'
"""
from fastapi import FastAPI

from app.routes.extract import router as extract_router

app = FastAPI(title="Day 4 — Structured output, retries, timeouts")
app.include_router(extract_router, tags=["extract"])


@app.get("/health")
async def health():
    return {"status": "ok"}