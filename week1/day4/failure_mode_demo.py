"""
failure_mode_demo.py — runs with ZERO third-party deps, no network.

It reimplements the EXACT decision logic from app/services/retry.py and
app/services/gemini.py (status-based retryability, exponential backoff + jitter,
two-layer timeout, self-correcting validation retry) so you can watch the
behaviour fire. The real code uses tenacity + google-genai; the rules are the same.

Three scenarios:
  A. Rate limit (429) -> retried with backoff+jitter, then succeeds
  B. Bad request (400) -> NOT retried, fails immediately
  C. Hanging call -> outer timeout fires (proving the safety net works)
"""
from __future__ import annotations

import asyncio
import random
import time

# ---- mirror of app/services/retry.py ----
RETRYABLE_STATUS_CODES = frozenset({408, 429, 500, 502, 503, 504})


class FakeAPIError(Exception):
    def __init__(self, code: int, message: str):
        self.code = code
        super().__init__(f"[{code}] {message}")


def is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, ConnectionError):
        return True
    if isinstance(exc, FakeAPIError):
        return exc.code in RETRYABLE_STATUS_CODES
    return False


async def call_with_retry(fn, *, max_attempts=4, base=1.0, cap=8.0):
    """Exponential backoff + FULL jitter, transient-only. Mirrors with_llm_retry."""
    attempt = 0
    while True:
        attempt += 1
        try:
            return await fn(attempt)
        except Exception as exc:
            if not is_retryable(exc) or attempt >= max_attempts:
                raise
            # exponential: base * 2^(attempt-1), capped
            backoff = min(cap, base * (2 ** (attempt - 1)))
            # FULL jitter: sleep a random point in [0, backoff]. This is what
            # smears a thundering herd across the window instead of lockstep.
            sleep = random.uniform(0, backoff)
            print(f"    attempt {attempt} failed ({exc}); "
                  f"backoff cap={backoff:.1f}s, jittered sleep={sleep:.2f}s")
            await asyncio.sleep(sleep)


# ---------- Scenario A: 429 then success ----------
async def scenario_rate_limit():
    print("\n=== A. Rate limit (429): retried with backoff+jitter ===")
    state = {"calls": 0}

    async def flaky(attempt):
        state["calls"] += 1
        if state["calls"] < 3:               # fail twice, succeed on the third
            raise FakeAPIError(429, "rate limited")
        return "OK (succeeded after retries)"

    result = await call_with_retry(flaky, base=0.2, cap=1.0)  # short delays for demo
    print(f"  -> {result} after {state['calls']} calls")


# ---------- Scenario B: 400 is never retried ----------
async def scenario_bad_request():
    print("\n=== B. Bad request (400): NOT retried, fails immediately ===")
    state = {"calls": 0}

    async def broken(attempt):
        state["calls"] += 1
        raise FakeAPIError(400, "malformed request")

    try:
        await call_with_retry(broken, base=0.2, cap=1.0)
    except FakeAPIError as e:
        print(f"  -> raised immediately: {e}; total calls = {state['calls']} "
              f"(correct: 1, never retried)")


# ---------- Scenario C: outer timeout fires on a hang ----------
async def scenario_timeout():
    print("\n=== C. Hanging call: outer asyncio.wait_for fires ===")

    async def hang(attempt):
        await asyncio.sleep(100)  # simulate a stuck call the inner timeout missed

    start = time.monotonic()
    try:
        # outer layer, in SECONDS — mirrors extract()'s wait_for
        await asyncio.wait_for(call_with_retry(hang), timeout=1.5)
    except asyncio.TimeoutError:
        elapsed = time.monotonic() - start
        print(f"  -> TimeoutError after {elapsed:.2f}s "
              f"(route maps this to HTTP 504)")


# ---------- Bonus: show jitter dispersing a herd ----------
async def scenario_thundering_herd():
    print("\n=== Bonus: jitter disperses a herd (10 clients, all fail at t=0) ===")
    cap = 4.0
    no_jitter = [min(cap, 1.0 * (2 ** 0))] * 10        # all wait exactly 1.0s
    with_jitter = [random.uniform(0, min(cap, 1.0)) for _ in range(10)]
    print(f"  without jitter, first-retry waits: {[f'{x:.2f}' for x in no_jitter]}")
    print(f"     -> all 10 retry at the SAME instant (herd reforms)")
    print(f"  with jitter,    first-retry waits: {[f'{x:.2f}' for x in with_jitter]}")
    print(f"     -> spread across the window (herd dispersed)")


async def main():
    await scenario_rate_limit()
    await scenario_bad_request()
    await scenario_timeout()
    await scenario_thundering_herd()
    print("\nAll scenarios complete.")


if __name__ == "__main__":
    asyncio.run(main())