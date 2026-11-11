"""Providers: the wire to the cheap models.

Stdlib only (`urllib`), matching the house style already set by
`zoth-fast/router_proxy.py`. Two implementations:

  * `OpenAICompatProvider` -- any OpenAI-compatible `/v1/chat/completions`.
    Retries 429/5xx honouring `Retry-After`, feeds rate-limit headers into the
    limiter, and returns the provider's exact `usage` (the Nous Portal includes
    `usage.cost` in USD, so spend is measured rather than estimated).

  * `MockProvider` -- deterministic, no network, no cost. Every test in this
    repo runs against it, so the suite is safe to run repeatedly and offline.
"""

from __future__ import annotations

import json
import random
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

from .ratelimit import AdaptiveRateLimiter, RetryPolicy


class ProviderError(RuntimeError):
    def __init__(self, message: str, status: int | None = None, retryable: bool = False,
                 retry_after: float | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.retryable = retryable
        self.retry_after = retry_after


@dataclass
class ChatResult:
    text: str
    usage: dict = field(default_factory=dict)
    model: str = ""
    latency_s: float = 0.0
    attempts: int = 1
    error: str | None = None


class BaseProvider:
    name = "base"

    def chat(self, model: str, messages: list[dict], *, temperature: float = 0.7,
             max_tokens: int = 1024, timeout_s: float = 120.0) -> ChatResult:
        raise NotImplementedError

    def chat_stream(self, model: str, messages: list[dict], *, temperature: float = 0.7,
                    max_tokens: int = 1024, timeout_s: float = 120.0):
        """Yield ('delta', text) chunks then ('usage', dict) exactly once."""
        res = self.chat(model, messages, temperature=temperature, max_tokens=max_tokens,
                        timeout_s=timeout_s)
        for i in range(0, len(res.text), 24):
            yield "delta", res.text[i:i + 24]
        yield "usage", res.usage

    def stats(self) -> dict:
        return {}


class OpenAICompatProvider(BaseProvider):
    name = "openai-compat"

    def __init__(
        self,
        base_url: str,
        api_key: str,
        limiter: AdaptiveRateLimiter | None = None,
        retry: RetryPolicy | None = None,
        user_agent: str = "zoth-egregore/1.0",
    ) -> None:
        if not base_url:
            raise ValueError("base_url is required")
        self.base_url = base_url.rstrip("/")
        if not self.base_url.endswith("/v1"):
            self.base_url += "/v1"
        self.api_key = api_key or ""
        self.limiter = limiter or AdaptiveRateLimiter()
        self.retry = retry or RetryPolicy()
        self.user_agent = user_agent
        self._lock = threading.Lock()
        self._counters = {"calls": 0, "errors": 0, "retries": 0, "tokens_in": 0,
                          "tokens_out": 0, "cost_usd": 0.0, "latency_s": 0.0}

    # -- internals ----------------------------------------------------------

    def _record(self, **deltas) -> None:
        with self._lock:
            for k, v in deltas.items():
                self._counters[k] = self._counters.get(k, 0) + v

    def _post(self, path: str, payload: dict, timeout_s: float, stream: bool):
        body = json.dumps(payload).encode()
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": self.user_agent,
            "Accept": "text/event-stream" if stream else "application/json",
        }
        req = urllib.request.Request(self.base_url + path, data=body, headers=headers)
        return urllib.request.urlopen(req, timeout=timeout_s)

    # -- public -------------------------------------------------------------

    def chat(self, model: str, messages: list[dict], *, temperature: float = 0.7,
             max_tokens: int = 1024, timeout_s: float = 120.0) -> ChatResult:
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        est_tokens = max(1, sum(len(str(m.get("content", ""))) for m in messages) // 4 + max_tokens)
        last_err: ProviderError | None = None
        t0 = time.time()

        for attempt in range(1, self.retry.attempts + 1):
            self.limiter.reserve(est_tokens)
            try:
                with self._post("/chat/completions", payload, timeout_s, False) as resp:
                    raw = resp.read().decode("utf-8", "replace")
                    hdrs = {k.lower(): v for k, v in resp.headers.items()}
                self.limiter.observe(hdrs, 200)
                data = json.loads(raw)
                text = self._extract_text(data)
                usage = data.get("usage") or {}
                self._record(
                    calls=1,
                    tokens_in=int(usage.get("prompt_tokens") or 0),
                    tokens_out=int(usage.get("completion_tokens") or 0),
                    cost_usd=float(usage.get("cost") or 0.0),
                    latency_s=time.time() - t0,
                )
                return ChatResult(text=text, usage=usage, model=model,
                                  latency_s=time.time() - t0, attempts=attempt)

            except urllib.error.HTTPError as e:
                hdrs = {k.lower(): v for k, v in (e.headers or {}).items()}
                self.limiter.observe(hdrs, e.code)
                detail = ""
                try:
                    detail = e.read().decode("utf-8", "replace")[:400]
                except Exception:
                    pass
                retryable = e.code in (408, 409, 425, 429, 500, 502, 503, 504)
                ra: float | None = None
                try:
                    if hdrs.get("retry-after"):
                        ra = float(str(hdrs["retry-after"]).strip())
                except ValueError:
                    ra = None
                last_err = ProviderError(f"HTTP {e.code}: {detail}", e.code, retryable, ra)
                self._record(errors=1)
                if not retryable or attempt == self.retry.attempts:
                    break
                self._record(retries=1)
                time.sleep(self.retry.delay_for(attempt, ra))

            except (urllib.error.URLError, TimeoutError, OSError) as e:
                last_err = ProviderError(f"{type(e).__name__}: {e}", None, True, None)
                self._record(errors=1)
                if attempt == self.retry.attempts:
                    break
                self._record(retries=1)
                time.sleep(self.retry.delay_for(attempt))

            except (ValueError, KeyError) as e:
                # malformed body: not retryable
                last_err = ProviderError(f"bad response: {e}", None, False, None)
                self._record(errors=1)
                break

        return ChatResult(text="", usage={}, model=model, latency_s=time.time() - t0,
                          attempts=self.retry.attempts,
                          error=str(last_err) if last_err else "unknown failure")

    def chat_stream(self, model: str, messages: list[dict], *, temperature: float = 0.7,
                    max_tokens: int = 1024, timeout_s: float = 120.0):
        """True token streaming. Falls back to a single chunked call if SSE fails."""
        payload = {
            "model": model, "messages": messages, "temperature": temperature,
            "max_tokens": max_tokens, "stream": True,
            "stream_options": {"include_usage": True},
        }
        est_tokens = max(1, sum(len(str(m.get("content", ""))) for m in messages) // 4 + max_tokens)
        self.limiter.reserve(est_tokens)
        usage: dict = {}
        got_any = False
        try:
            with self._post("/chat/completions", payload, timeout_s, True) as resp:
                hdrs = {k.lower(): v for k, v in resp.headers.items()}
                self.limiter.observe(hdrs, 200)
                for raw_line in resp:
                    line = raw_line.decode("utf-8", "replace").strip()
                    if not line or not line.startswith("data:"):
                        continue
                    chunk = line[5:].strip()
                    if chunk == "[DONE]":
                        break
                    try:
                        obj = json.loads(chunk)
                    except ValueError:
                        continue
                    if obj.get("usage"):
                        usage = obj["usage"]
                    for choice in obj.get("choices") or []:
                        piece = (choice.get("delta") or {}).get("content")
                        if piece:
                            got_any = True
                            yield "delta", piece
        except Exception as e:  # noqa: BLE001 - fall back rather than fail the request
            if not got_any:
                res = self.chat(model, messages, temperature=temperature,
                                max_tokens=max_tokens, timeout_s=timeout_s)
                for i in range(0, len(res.text), 24):
                    yield "delta", res.text[i:i + 24]
                yield "usage", res.usage
                return
            yield "usage", {"error": str(e)}
            return

        self._record(calls=1,
                     tokens_in=int(usage.get("prompt_tokens") or 0),
                     tokens_out=int(usage.get("completion_tokens") or 0),
                     cost_usd=float(usage.get("cost") or 0.0))
        yield "usage", usage

    @staticmethod
    def _extract_text(data: dict) -> str:
        choices = data.get("choices") or []
        if not choices:
            raise KeyError("no choices in response")
        msg = choices[0].get("message") or {}
        text = msg.get("content")
        if text is None:
            text = choices[0].get("text") or ""
        # some providers put reasoning in a separate field; keep only content
        return str(text).strip()

    def stats(self) -> dict:
        with self._lock:
            return dict(self._counters)


# ---------------------------------------------------------------------------
# Mock
# ---------------------------------------------------------------------------


class MockProvider(BaseProvider):
    """Deterministic offline provider. `responder` maps messages -> text.

    Used by the whole test suite: it can be made to disagree, to fail with 429
    a fixed number of times, or to be slow -- so the rate limiter, retry logic
    and escalation policy are all exercised without touching the network.
    """

    name = "mock"

    def __init__(self, responder=None, latency_s: float = 0.0, fail_429_times: int = 0,
                 cost_per_call: float = 0.0) -> None:
        self.responder = responder or self._default_responder
        self.latency_s = latency_s
        self.fail_429_times = fail_429_times
        self.cost_per_call = cost_per_call
        self._lock = threading.Lock()
        self.calls: list[dict] = []
        self._failures = 0

    def _default_responder(self, model: str, messages: list[dict]) -> str:
        system = messages[0].get("content", "") if messages else ""
        prompt = messages[-1].get("content", "") if messages else ""
        tag = system.split("Your lens: ")[-1].split("\n")[0] if "Your lens: " in system else "GENERIC"
        return f"[{tag}] answer to {prompt[:40]}"

    def chat(self, model: str, messages: list[dict], *, temperature: float = 0.7,
             max_tokens: int = 1024, timeout_s: float = 120.0) -> ChatResult:
        with self._lock:
            self.calls.append({"model": model, "messages": messages, "t": time.time()})
            if self._failures < self.fail_429_times:
                self._failures += 1
                err = True
            else:
                err = False
        if err:
            # emulate the retry loop's contract by returning an error result
            return ChatResult(text="", usage={}, model=model, error="HTTP 429: mock rate limit",
                              attempts=1)
        if self.latency_s:
            time.sleep(self.latency_s)
        text = self.responder(model, messages)
        usage = {"prompt_tokens": 50, "completion_tokens": 20, "cost": self.cost_per_call}
        return ChatResult(text=text, usage=usage, model=model, latency_s=self.latency_s)

    def stats(self) -> dict:
        return {"calls": len(self.calls)}
