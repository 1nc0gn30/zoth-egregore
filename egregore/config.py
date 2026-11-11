"""Configuration and credential discovery for EGREGORE.

Defaults are grounded in real measurements taken from the Nous Portal on
2026-11-10, not guesses:

    x-ratelimit-limit-requests      = 400      (per 60s)
    x-ratelimit-limit-tokens        = 4_000_000 (per 60s)
    x-ratelimit-limit-requests-1h   = 16800
    x-ratelimit-limit-tokens-1h     = 168_000_000

400 requests/minute is the real ceiling on fan-out width, which is why the
engine escalates in waves instead of spawning everything at once.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

HOME = Path(os.path.expanduser("~"))
HERMES_DIR = Path(os.environ.get("HERMES_HOME", HOME / ".hermes"))
HERMES_AUTH = HERMES_DIR / "auth.json"
STATE_DIR = Path(os.environ.get("EGREGORE_STATE_DIR", HOME / ".local/state/egregore"))

# ---------------------------------------------------------------------------
# Model tiers
# ---------------------------------------------------------------------------

# Cheap, fast, high-throughput: the fan-out. Every one of the N agents calls
# this model. `:free` ids cost literally nothing on the portal today.
#
# ONE model by default, deliberately. Self-MoA (arXiv:2502.00674) found that
# aggregating many outputs from the single best model beats mixing different
# models, because mixing drags the average quality of the proposals down --
# it measured +6.6% on AlpacaEval 2.0 and +3.8% average across MMLU/CRUX/MATH
# for Self-MoA over standard MoA. Diversity here comes from the LENS (a
# different archetype/domain/stance each mind argues from), not from swapping
# vendors under the swarm. The pool below is opt-in via EGREGORE_SCOUT_POOL.
SCOUT_MODELS = [
    "stepfun/step-3.7-flash:free",
    "upstage/solar-mini4:free",
    "meituan/longcat-2.5:free",
    "deepseek/deepseek-v4.1-flash",
    "z-ai/glm-5.3-flash",
    "google/gemini-3.5-flash-lite",
]

# Strong model used exactly once per request, to collapse N answers into one.
SYNTH_MODELS = [
    "deepseek/deepseek-v4-pro",
    "deepseek/deepseek-v4.1-flash",
]

# Fallback price table, USD per 1M tokens, used ONLY when the provider does not
# return an exact `usage.cost`. The Nous Portal does return it, so this is a
# safety net, not the accounting path.
PRICE_TABLE = {
    "__default__": (0.20, 0.60),
    "deepseek/deepseek-v4-pro": (0.55, 2.19),
    "deepseek/deepseek-v4.1-flash": (0.17, 0.17),
    "deepseek/deepseek-v4-flash": (0.17, 0.17),
}


def is_free(model: str) -> bool:
    return model.endswith(":free")


# ---------------------------------------------------------------------------
# Credentials
# ---------------------------------------------------------------------------


def discover_nous_credentials() -> tuple[str | None, str | None]:
    """Return (base_url, api_key) from the Hermes profile, if present.

    Reads ~/.hermes/auth.json, top-level `providers.nous`. Only the
    inference base URL and the short-lived agent key are used; nothing is
    written back and nothing is logged.
    """
    if not HERMES_AUTH.exists():
        return None, None
    try:
        data = json.loads(HERMES_AUTH.read_text())
    except Exception:
        return None, None
    nous = (data.get("providers") or {}).get("nous") or {}
    base = nous.get("inference_base_url") or nous.get("portal_base_url")
    key = nous.get("agent_key") or nous.get("access_token")
    if base and not str(base).rstrip("/").endswith("/v1"):
        base = str(base).rstrip("/") + "/v1"
    return (base or None), (key or None)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


@dataclass
class EgregoreConfig:
    # --- provider ---
    base_url: str = ""
    api_key: str = ""
    scout_model: str = SCOUT_MODELS[0]
    # Opt-in: rotate these across minds instead of using one model. Only worth
    # it when the pool members are genuinely comparable in quality.
    scout_pool: list[str] = field(default_factory=list)
    synth_model: str = SYNTH_MODELS[0]
    timeout_s: float = 120.0
    max_tokens: int = 1024
    temperature: float = 0.7

    # --- swarm shape ---
    # Wave 1 is deliberately small: a cheap probe of how much the task even
    # disagrees with itself. Only disagreeable tasks earn more agents.
    seed_agents: int = 8
    escalation_factor: float = 3.0
    stop_agreement: float = 0.72       # >= this and we stop early (fast path)
    stop_agreement_floor: float = 0.45  # below this we keep escalating hard
    # Adaptive-Consistency (arXiv:2305.11860): stop the moment the Beta
    # posterior says the leading answer is safe. tau=0.95 is their C_thresh.
    stop_confidence: float = 0.95
    esc_window: int = 4                # ESC: this many identical answers in a row
    consensus_min_samples: int = 6     # never let the posterior stop before this many
    min_agents: int = 50
    max_agents: int = 1000
    force_min_waves: int = 1           # waves to run before early-stop is allowed

    # --- rate limiting ---
    max_concurrency: int = 64
    rpm_limit: int = 400               # measured
    tpm_limit: int = 4_000_000         # measured
    safety_margin: float = 0.90        # stay under the ceiling
    adaptive: bool = True              # learn limits from response headers

    # --- retries ---
    retry_attempts: int = 4
    retry_base_s: float = 0.75
    retry_max_s: float = 30.0

    # --- budget ---
    max_usd_per_request: float = 0.50
    max_usd_per_day: float = 5.00

    # --- misc ---
    cache_enabled: bool = True
    cache_path: Path = field(default_factory=lambda: STATE_DIR / "cache.sqlite3")
    ledger_path: Path = field(default_factory=lambda: STATE_DIR / "ledger.jsonl")
    daily_path: Path = field(default_factory=lambda: STATE_DIR / "daily.json")
    port: int = 8147
    model_id: str = "zoth-egregore"

    def __post_init__(self) -> None:
        if not self.base_url or not self.api_key:
            base, key = discover_nous_credentials()
            self.base_url = self.base_url or base or ""
            self.api_key = self.api_key or key or ""
        self.base_url = self.base_url.rstrip("/")

    # -- construction helpers -------------------------------------------------

    @classmethod
    def from_env(cls, **overrides) -> "EgregoreConfig":
        cfg = cls()
        env_map = {
            "EGREGORE_BASE_URL": "base_url",
            "EGREGORE_API_KEY": "api_key",
            "EGREGORE_SCOUT_MODEL": "scout_model",
            "EGREGORE_SYNTH_MODEL": "synth_model",
            "EGREGORE_MAX_AGENTS": "max_agents",
            "EGREGORE_MIN_AGENTS": "min_agents",
            "EGREGORE_CONCURRENCY": "max_concurrency",
            "EGREGORE_RPM": "rpm_limit",
            "EGREGORE_TPM": "tpm_limit",
            "EGREGORE_MAX_USD_REQUEST": "max_usd_per_request",
            "EGREGORE_MAX_USD_DAY": "max_usd_per_day",
            "EGREGORE_PORT": "port",
        }
        for env, attr in env_map.items():
            raw = os.environ.get(env)
            if raw is None or raw == "":
                continue
            cur = getattr(cfg, attr)
            try:
                if isinstance(cur, int) and not isinstance(cur, bool):
                    setattr(cfg, attr, int(raw))
                elif isinstance(cur, float):
                    setattr(cfg, attr, float(raw))
                else:
                    setattr(cfg, attr, raw)
            except ValueError:
                pass
        for k, v in overrides.items():
            if v is not None and hasattr(cfg, k):
                setattr(cfg, k, v)
        pool = os.environ.get("EGREGORE_SCOUT_POOL", "")
        if pool.strip():
            cfg.scout_pool = [m.strip() for m in pool.split(",") if m.strip()]
        cfg.__post_init__()
        return cfg

    def scout_model_for(self, index: int) -> str:
        """Which model mind `index` calls.

        One model unless a pool was explicitly configured (Self-MoA, see the
        SCOUT_MODELS comment). Keeps the default honest: the swarm's diversity
        is in the lenses, and its quality is the model's.
        """
        if not self.scout_pool:
            return self.scout_model
        return self.scout_pool[index % len(self.scout_pool)]

    def validate(self) -> list[str]:
        problems = []
        if not self.base_url:
            problems.append("no provider base_url (set EGREGORE_BASE_URL or log in to Hermes)")
        if not self.api_key:
            problems.append("no provider api_key (set EGREGORE_API_KEY or log in to Hermes)")
        if self.max_agents < self.min_agents:
            problems.append(f"max_agents ({self.max_agents}) < min_agents ({self.min_agents})")
        if self.max_concurrency < 1:
            problems.append("max_concurrency must be >= 1")
        return problems

    def public(self) -> dict:
        d = asdict(self)
        d["api_key"] = "***" if self.api_key else ""
        d["cache_path"] = str(self.cache_path)
        d["ledger_path"] = str(self.ledger_path)
        d["daily_path"] = str(self.daily_path)
        return d
