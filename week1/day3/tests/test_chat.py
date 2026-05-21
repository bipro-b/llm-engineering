"""
tests/test_chat.py
==================
Smoke tests for /chat and /chat/stream. Run with:
    python -m pytest -q

No API key required: we override get_llm_service with a FakeLLM.
"""

import os
from typing import AsyncIterator

os.environ.setdefault("GEMINI_API_KEY", "test-key-not-real")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.routes.chat import get_llm_service  # noqa: E402
from app.schemas.chat import ChatRequest, ChatResponse, Usage  # noqa: E402
from app.schemas.stream import StreamDelta, StreamEvent, StreamUsage  # noqa: E402


class FakeLLM:
    """Stand-in for LLMService. Implements both chat() and stream()."""

    def __init__(self, chunks: list[str] | None = None) -> None:
        self.calls: list[ChatRequest] = []
        self.chunks = chunks if chunks is not None else ["Hello", " ", "world", "!"]

    async def chat(self, req: ChatRequest) -> ChatResponse:
        self.calls.append(req)
        return ChatResponse(
            model=req.model or "fake-model",
            content="".join(self.chunks),
            stop_reason="STOP",
            usage=Usage(input_tokens=10, output_tokens=5),
        )

    def stream(self, req: ChatRequest) -> AsyncIterator[StreamEvent]:
        self.calls.append(req)
        return self._gen()

    async def _gen(self) -> AsyncIterator[StreamEvent]:
        for c in self.chunks:
            yield StreamDelta(text=c)
        yield StreamUsage(input_tokens=10, output_tokens=len(self.chunks))


def _client_with_fake(chunks: list[str] | None = None) -> tuple[TestClient, FakeLLM]:
    fake = FakeLLM(chunks=chunks)
    app.dependency_overrides[get_llm_service] = lambda: fake
    return TestClient(app), fake


def test_health() -> None:
    client, _ = _client_with_fake()
    assert client.get("/health").json() == {"status": "ok"}


def test_chat_happy_path() -> None:
    client, _ = _client_with_fake()
    r = client.post(
        "/chat",
        json={"messages": [{"role": "user", "content": "hi"}], "temperature": 0.3,
              "max_tokens": 50},
    )
    assert r.status_code == 200, r.text
    assert r.json()["content"] == "Hello world!"


def test_chat_rejects_bad_temperature() -> None:
    client, _ = _client_with_fake()
    r = client.post(
        "/chat",
        json={"messages": [{"role": "user", "content": "hi"}], "temperature": 9},
    )
    assert r.status_code == 422


def test_chat_stream_emits_delta_usage_done() -> None:
    """Smoke-test the SSE format: deltas, then usage, then [DONE]."""
    client, _ = _client_with_fake(chunks=["foo", "bar"])
    with client.stream(
        "POST",
        "/chat/stream",
        json={"messages": [{"role": "user", "content": "hi"}], "max_tokens": 50},
    ) as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        body = b"".join(resp.iter_bytes()).decode("utf-8")

    # Split into SSE events (separated by blank lines).
    events = [e for e in body.split("\n\n") if e.strip()]
    # Every event is `data: <payload>`.
    payloads = [e.removeprefix("data: ") for e in events]

    # We expect at least: delta("foo"), delta("bar"), usage, [DONE].
    assert payloads[-1] == "[DONE]"
    # First two payloads are deltas (JSON).
    assert '"type":"delta"' in payloads[0] and '"foo"' in payloads[0]
    assert '"type":"delta"' in payloads[1] and '"bar"' in payloads[1]
    # Some payload before [DONE] is a usage event.
    assert any('"type":"usage"' in p for p in payloads[:-1])


def test_static_root_redirects_to_demo() -> None:
    client, _ = _client_with_fake()
    r = client.get("/", follow_redirects=False)
    assert r.status_code in (302, 307)
    assert r.headers["location"] == "/static/index.html"