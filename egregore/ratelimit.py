"""Header-driven adaptive rate limiting.

The fan-out is limited by the provider's *requests per minute*, not by money:
the Nous Portal allows 400 RPM / 4M TPM, so a 1000-agent wave needs at least
150 seconds of wall clock no matter how clever the code is. Two things follow:

1. Spawning 1000 requests at once is pointless -- it just produces 600 429s.
   The limiter reserves capacity *before* each call, so the pool drains at
   exactly the rate the provider accepts.

2. The limits are not static. Every response carries the provider's own truth
   (`x-ratelimit-remaining-requests`, `x-ratelimit-reset-requests`,
   `retry-after`), so `observe()` folds those numbers back in and the limiter
   tightens or relaxes itself around the real quota instead of a guess.
"""

from __future__ import annotations

import random
import threading
import time
from collections import deque
from dataclasses import dataclass


class AdaptiveRateLimiter:
    """Sliding-window limiter for requests AND tokens, self-tuning from headers."""

    def __init__(
        self,
        rpm: int = 400,
        tpm: int = 4_000_000,
        safety_margin: float = 0.90,
        adaptive: bool = True,
        window_s: float = 60.0,
    ) -> None:
        self.rpm = max(1, rpm)
        self.tpm = max(1, tpm)
        self.safety_margin = safety_margin
        self.adaptive = adaptive
        self.window_s = window_s

        self._events: deque[tuple[float, int]] = deque()  # (ts, tokens)
        self._lock = threading.Lock()
        self._not_before = 0.0  # absolute time a hard server signal pins us to
        self._server_remaining_req: int | None = None
        self._server_remaining_tok: int | None = None
        self.observed = {"header_updates": 0, "429s": 0, "waits": 0, "wait_s": 0.0}

    # -- accounting ---------------------------------------------------------

    def _prune(self, now: float) -> None:
        cutoff = now - self.window_s
        ev = self._events
        while ev and ev[0][0] < cutoff:
            ev.popleft()

    def _used(self) -> tuple[int, int]:
        return len(self._events), sum(e[1] for e in self._events)

    # -- reservation --------------------------------------------------------

    def reserve(self, est_tokens: int = 0, max_wait_s: float = 600.0) -> float:
        """Block until capacity for one request is available. Returns seconds waited."""
        est_tokens = max(0, int(est_tokens))
        started = time.monotonic()
        slept_total = 0.0

        while True:
            now = time.monotonic()
            with self._lock:
                self._prune(now)
                used_r, used_t = self._used()
                cap_r = int(self.rpm * self.safety_margin)
                cap_t = int(self.tpm * self.safety_margin)

                wait = 0.0
                # hard signal from the server: respect it absolutely
                if self._not_before > now:
                    wait = self._not_before - now
                # per-minute request ceiling
                if used_r + 1 > cap_r and self._events:
                    wait = max(wait, self._events[0][0] + self.window_s - now)
                # per-minute token ceiling
                if used_t + est_tokens > cap_t and self._events:
                    wait = max(wait, self._events[0][0] + self.window_s - now)
                # server told us we are nearly out of requests
                if self._server_remaining_req is not None and self._server_remaining_req <= 0:
                    wait = max(wait, 1.0)

                if wait <= 0.0:
                    self._events.append((now, est_tokens))
                    return slept_total
                if slept_total + wait > max_wait_s:
                    # Give up waiting; caller will hit a normal 429 path.
                    self._events.append((now, est_tokens))
                    return slept_total

            sleep = min(wait, 2.0) + random.uniform(0, 0.05)
            time.sleep(sleep)
            slept_total += sleep
            if slept_total > (time.monotonic() - started) + 1.0:
                slept_total = time.monotonic() - started

    # -- server feedback ----------------------------------------------------

    def observe(self, headers: dict, status: int = 200) -> None:
        """Fold the provider's own rate-limit headers back into the limiter."""
        if not headers:
            return
        h = {str(k).lower(): v for k, v in headers.items()}

        def num(key: str) -> float | None:
            raw = h.get(key)
            if raw is None:
                return None
            try:
                return float(str(raw).strip().strip('"'))
            except (TypeError, ValueError):
                return None

        with self._lock:
            self.observed["header_updates"] += 1
            if status == 429:
                self.observed["429s"] += 1

            if self.adaptive:
                lim_r = num("x-ratelimit-limit-requests")
                lim_t = num("x-ratelimit-limit-tokens")
                if lim_r and lim_r > 0:
                    # Trust the server's ceiling; never raise ours above it.
                    self.rpm = int(min(lim_r, self.rpm) if self.rpm else lim_r)
                if lim_t and lim_t > 0:
                    self.tpm = int(min(lim_t, self.tpm) if self.tpm else lim_t)

            rem_r = num("x-ratelimit-remaining-requests")
            rem_t = num("x-ratelimit-remaining-tokens")
            self._server_remaining_req = int(rem_r) if rem_r is not None else None
            self._server_remaining_tok = int(rem_t) if rem_t is not None else None

            if status == 429:
                retry_after = num("retry-after")
                reset_r = num("x-ratelimit-reset-requests")
                backoff = retry_after or reset_r or 1.0
                self._not_before = max(self._not_before, time.monotonic() + float(backoff))
            elif rem_r is not None and rem_r <= 0:
                reset_r = num("x-ratelimit-reset-requests") or 1.0
                self._not_before = max(self._not_before, time.monotonic() + float(reset_r))

    # -- introspection ------------------------------------------------------

    def snapshot(self) -> dict:
        now = time.monotonic()
        with self._lock:
            self._prune(now)
            used_r, used_t = self._used()
            return {
                "rpm_limit": self.rpm,
                "tpm_limit": self.tpm,
                "used_requests_window": used_r,
                "used_tokens_window": used_t,
                "server_remaining_requests": self._server_remaining_req,
                "server_remaining_tokens": self._server_remaining_tok,
                "pinned_until_s": max(0.0, round(self._not_before - now, 3)),
                **{k: (round(v, 3) if isinstance(v, float) else v) for k, v in self.observed.items()},
            }


# ---------------------------------------------------------------------------
# Retry
# ---------------------------------------------------------------------------


@dataclass
class RetryPolicy:
    attempts: int = 4
    base_s: float = 0.75
    max_s: float = 30.0
    jitter: bool = True

    def delay_for(self, attempt: int, retry_after: float | None = None) -> float:
        """Exponential backoff with full jitter; honour Retry-After when given."""
        if retry_after is not None and retry_after > 0:
            return min(float(retry_after), self.max_s)
        raw = self.base_s * (2 ** max(0, attempt - 1))
        raw = min(raw, self.max_s)
        if self.jitter:
            # full jitter: anywhere in [raw/2, raw]
            return raw * (0.5 + random.random() * 0.5)
        return raw
