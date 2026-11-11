"""Spend control.

The engine must never be able to surprise the operator with a bill. Two hard
ceilings apply -- per request and per rolling day -- and both are enforced
*before* a wave is dispatched, so an escalation decision is made against
remaining budget rather than discovered after the fact.

The Nous Portal returns an exact `usage.cost` (USD) on every response, so
accounting here is measured spend, not an estimate. The price table in
config.PRICE_TABLE is only consulted when a provider omits that field.
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from .config import PRICE_TABLE, is_free


def estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Fallback USD estimate, used only when the provider omits usage.cost."""
    if is_free(model):
        return 0.0
    inp, out = PRICE_TABLE.get(model, PRICE_TABLE["__default__"])
    return (prompt_tokens / 1_000_000.0) * inp + (completion_tokens / 1_000_000.0) * out


class BudgetExceeded(RuntimeError):
    """Raised when a dispatch would breach a configured ceiling."""


@dataclass
class BudgetState:
    request_spent: float = 0.0
    day_spent: float = 0.0
    day: str = ""
    calls: int = 0
    denied: int = 0


class BudgetGuard:
    """Thread-safe per-request + per-day USD ceiling."""

    def __init__(
        self,
        max_usd_request: float = 0.50,
        max_usd_day: float = 5.00,
        daily_path: Path | None = None,
    ) -> None:
        self.max_usd_request = float(max_usd_request)
        self.max_usd_day = float(max_usd_day)
        self.daily_path = Path(daily_path) if daily_path else None
        self._lock = threading.Lock()
        self._state = BudgetState(day=self._today())
        self._load()

    # -- persistence --------------------------------------------------------

    @staticmethod
    def _today() -> str:
        return time.strftime("%Y-%m-%d", time.gmtime())

    def _load(self) -> None:
        if not self.daily_path or not self.daily_path.exists():
            return
        try:
            raw = json.loads(self.daily_path.read_text())
        except Exception:
            return
        if raw.get("day") == self._state.day:
            self._state.day_spent = float(raw.get("day_spent", 0.0))
            self._state.calls = int(raw.get("calls", 0))

    def _persist(self) -> None:
        if not self.daily_path:
            return
        try:
            self.daily_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.daily_path.with_suffix(".tmp")
            tmp.write_text(json.dumps({"day": self._state.day, "day_spent": self._state.day_spent,
                                       "calls": self._state.calls, "updated": time.time()}))
            tmp.replace(self.daily_path)
        except Exception:
            pass

    def _roll_day(self) -> None:
        today = self._today()
        if today != self._state.day:
            self._state.day = today
            self._state.day_spent = 0.0
            self._state.calls = 0

    # -- gating -------------------------------------------------------------

    def check(self, projected_usd: float = 0.0) -> tuple[bool, str]:
        """May we spend `projected_usd` more right now?"""
        with self._lock:
            self._roll_day()
            if self._state.request_spent + projected_usd > self.max_usd_request:
                self._state.denied += 1
                return False, (f"per-request ceiling: spent ${self._state.request_spent:.6f} + "
                               f"${projected_usd:.6f} > ${self.max_usd_request:.6f}")
            if self._state.day_spent + projected_usd > self.max_usd_day:
                self._state.denied += 1
                return False, (f"per-day ceiling: spent ${self._state.day_spent:.6f} + "
                               f"${projected_usd:.6f} > ${self.max_usd_day:.6f}")
            return True, "ok"

    def settle(self, model: str, usage: dict | None, cost_usd: float | None = None) -> float:
        """Record actual spend. Returns the amount charged to this request."""
        usage = usage or {}
        if cost_usd is None:
            cost_usd = usage.get("cost")
        if cost_usd is None:
            cost_usd = estimate_cost(
                model,
                int(usage.get("prompt_tokens") or 0),
                int(usage.get("completion_tokens") or 0),
            )
        cost_usd = float(cost_usd)
        with self._lock:
            self._roll_day()
            self._state.request_spent += cost_usd
            self._state.day_spent += cost_usd
            self._state.calls += 1
            self._persist()
        return cost_usd

    def new_request(self) -> None:
        with self._lock:
            self._state.request_spent = 0.0

    # -- introspection ------------------------------------------------------

    @property
    def request_spent(self) -> float:
        with self._lock:
            return self._state.request_spent

    @property
    def day_spent(self) -> float:
        with self._lock:
            return self._state.day_spent

    def remaining_request(self) -> float:
        return max(0.0, self.max_usd_request - self.request_spent)

    def remaining_day(self) -> float:
        return max(0.0, self.max_usd_day - self.day_spent)

    def snapshot(self) -> dict:
        return {
            "request_spent_usd": round(self.request_spent, 6),
            "request_limit_usd": self.max_usd_request,
            "day_spent_usd": round(self.day_spent, 6),
            "day_limit_usd": self.max_usd_day,
            "day": self._state.day,
            "calls": self._state.calls,
            "denied": self._state.denied,
        }
