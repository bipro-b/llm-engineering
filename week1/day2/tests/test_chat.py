"""
tests/test_chat.py
==================
Smoke tests. Run with: `python -m pytest -q`

These tests run WITHOUT a real API key — we swap the LLMService for a fake
using FastAPI's dependency_overrides. Same pattern from yesterday; only the
required env var changed (ANTHROPIC_API_KEY -> GEMINI_API_KEY).
"""

import os

os.environ.setdefault("GEMINI_API_KEY", "test-key-not-real")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.routes.chat import get_llm_service  # noqa: E402
from app.schemas.chat import ChatRequest, ChatResponse, Usage  # noqa: E402


class FakeLLM:
    """Stand-in for LLMService. Returns a canned response, records the call."""

    def __init__(self) -> None:
        self.calls: list[ChatRequest] = []

    async def chat(self, req: ChatRequest) -> ChatResponse:
        self.calls.append(req)
        return ChatResponse(
            model=req.model or "fake-model",
            content=f"echo: {req.messages[-1].content}",
            stop_reason="STOP",
            usage=Usage(input_tokens=10, output_tokens=5),
        )


def _client_with_fake() -> tuple[TestClient, FakeLLM]:
    fake = FakeLLM()
    app.dependency_overrides[get_llm_service] = lambda: fake
    return TestClient(app), fake


def test_health() -> None:
    client, _ = _client_with_fake()
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_chat_happy_path() -> None:
    client, fake = _client_with_fake()
    body = {
        "messages": [{"role": "user", "content": "hello"}],
        "temperature": 0.3,
        "max_tokens": 50,
    }
    r = client.post("/chat", json=body)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["content"] == "echo: hello"
    assert data["usage"]["input_tokens"] == 10
    assert len(fake.calls) == 1


def test_chat_rejects_bad_temperature() -> None:
    client, _ = _client_with_fake()
    r = client.post(
        "/chat",
        json={"messages": [{"role": "user", "content": "hi"}], "temperature": 9},
    )
    assert r.status_code == 422
    assert any("temperature" in str(d.get("loc", "")) for d in r.json()["detail"])


def test_chat_rejects_empty_messages() -> None:
    client, _ = _client_with_fake()
    r = client.post("/chat", json={"messages": []})
    assert r.status_code == 422