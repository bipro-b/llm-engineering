# Day 3 Notes — Streaming

## Setup
- Built `/chat/stream` returning SSE.
- Streaming events: `StreamDelta` (text), `StreamUsage` (token counts), `StreamError`.
- Demo page at `/` consumes the stream via `fetch + ReadableStream`.
- Disconnect handled via `request.is_disconnected()` checked once per chunk.

## Concrete numbers I observed
- TTFT (time-to-first-token) shown on the demo page: ___ ms
- Total time for a ~___-token answer: ___ ms
- Effective tokens/sec: ___

## Observation 1 — Streaming changes perceived latency
Without streaming, a 600-token answer feels broken because you stare at a
spinner for ___ seconds. With streaming, the first token appears in ___ ms
and the experience feels alive even though *total* time is identical.

## Observation 2 — Disconnect handling and cost
When a client disconnects mid-stream, who pays for what?

Fill in the chain:
1. The client closes the TCP connection. FastAPI / Starlette notices this
   and `request.is_disconnected()` will return `True` on its next check.
2. In `_sse_event_stream` (routes/chat.py), the check between events
   causes us to `break` out of the async-for loop.
3. Breaking out causes the underlying async generator (the provider's
   `stream()`) to be garbage-collected. Python raises `GeneratorExit`
   inside it at the `yield`.
4. That cancellation propagates into the SDK's async iterator
   (`generate_content_stream`), which closes its underlying HTTP
   connection to Google.
5. Once Google sees the HTTP stream close, it stops generating.
   Tokens not yet generated are NOT billed.

**What I tested:** stopped the demo mid-stream on a 1024-token request.
Server log printed `sse: client disconnected, cancelling upstream` within
___ ms. The usage event (when one did arrive before disconnect) showed
output_tokens = ___ instead of the full 1024.

**What this means for product cost:** if my product has 10% of users
closing tabs at the median half-way point on a 500-token answer, naive
billing would be ~50 wasted tokens × 10% = 5 wasted output tokens per
request on average. At Gemini Flash output prices that's tiny, at Claude
Opus prices ($75/Mtok output) it adds up — roughly $0.0004 per disconnected
user, or $40/day at 100k requests/day at 10% disconnect. Not catastrophic,
but real money — and the fix is one line of code: `if await
request.is_disconnected(): break`.

## Observation 3 — SSE quirks worth remembering
- Blank line (`\n\n`) is the event separator. Single newline = invisible bug.
- `X-Accel-Buffering: no` header needed for nginx in production.
- `Cache-Control: no-cache` needed; some proxies will otherwise cache and
  hold the stream.
- `EventSource` (browser API) only supports GET. We POST a JSON body, so we
  parse SSE manually from `fetch().body.getReader()`. The demo page shows
  the ~30-line parser.

## Things still fuzzy
-
What broke:
-
What I want to dig into next:
-