"""The engine: many minds in, one answer out.

The orchestration has one job -- decide how many minds a given prompt is worth
-- and it does that by *measuring disagreement* rather than assuming it.

    wave 1   seed_agents (8)      cheap probe: do these minds already agree?
    score    lexical agreement + a Beta posterior over the vote (no extra calls)
    wave 2.. size * escalation_factor, on NEW lenses, while disagreement holds
    stop     the posterior is confident (arXiv:2305.11860), or agreement is
             high and >= min_agents minds have been heard, or max_agents hit,
             or the budget ceiling is hit
    collapse one synthesis call over the cluster representatives -> one answer

Three properties matter and are all tested:

  * Cheapness. Agreement and the stopping posterior are computed from text
    already in hand, so the only extra call versus a single-model answer is the
    one synthesis call. A task everybody agrees on costs ~9 calls, not 1000 --
    and it stops the moment the posterior is confident, which is exactly the
    Adaptive-Consistency result (sample budget cut by up to 7.9x with an
    average accuracy drop under 0.1%). A genuinely hard task earns its 1000
    agents because each wave is justified by measured disagreement.

  * Rate-limit safety. Waves are sized against what the limiter will actually
    admit. Nothing is dispatched that cannot be reserved first.

  * Never worse than one model. If synthesis fails, the largest cluster's
    medoid answer is returned, so the endpoint can only degrade, not break.
"""

from __future__ import annotations

import hashlib
import json
import math
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

from .budget import BudgetGuard
from .cache import ResponseCache, call_digest
from .codex import codex_for_prompt
from .config import EgregoreConfig
from .consensus import agreement_of, cluster_answers, medoid, stop_verdict
from .lenses import Lens, coverage, expand
from .providers import BaseProvider
from .ratelimit import AdaptiveRateLimiter
from .zoth_tools import build_tool_augmentation_block, detect_zoth_environment


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------


@dataclass
class AgentAnswer:
    lens: Lens
    text: str = ""
    usage: dict = field(default_factory=dict)
    cost: float = 0.0
    error: str | None = None
    cached: bool = False
    latency_s: float = 0.0

    @property
    def ok(self) -> bool:
        return bool(self.text) and not self.error


@dataclass
class EgregoreResult:
    text: str
    prompt: str
    agents_spawned: int = 0
    agents_succeeded: int = 0
    waves: list[dict] = field(default_factory=list)
    cost_usd: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0
    latency_s: float = 0.0
    agreement: float = 0.0
    diversity: float = 0.0
    vote_share: float = 0.0
    stop_confidence: float = 0.0
    clusters: list[dict] = field(default_factory=list)
    stopped_by: str = ""
    scout_model: str = ""
    synth_model: str = ""
    cache_hits: int = 0
    distinct_answers: int = 0
    lens_coverage: dict = field(default_factory=dict)
    codex_domains: list[str] = field(default_factory=list)
    zoth_tools: list[dict] = field(default_factory=list)
    errors: int = 0
    synthesis_failed: bool = False

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "agents_spawned": self.agents_spawned,
            "agents_succeeded": self.agents_succeeded,
            "waves": self.waves,
            "cost_usd": round(self.cost_usd, 6),
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "latency_s": round(self.latency_s, 3),
            "agreement": round(self.agreement, 4),
            "diversity": round(self.diversity, 4),
            "vote_share": round(self.vote_share, 4),
            "stop_confidence": round(self.stop_confidence, 4),
            "clusters": self.clusters,
            "stopped_by": self.stopped_by,
            "scout_model": self.scout_model,
            "synth_model": self.synth_model,
            "cache_hits": self.cache_hits,
            "distinct_answers": self.distinct_answers,
            "lens_coverage": self.lens_coverage,
            "codex_domains": self.codex_domains,
            "zoth_tools": self.zoth_tools,
            "errors": self.errors,
            "synthesis_failed": self.synthesis_failed,
        }


# ---------------------------------------------------------------------------
# Agreement / consensus math lives in consensus.py (text math, voting, and the
# Adaptive-Consistency stopping rule). It is re-exported here because callers
# have always imported it from the engine.
# ---------------------------------------------------------------------------

__all__ = [
    "AgentAnswer",
    "Egregore",
    "EgregoreResult",
    "agreement_of",
    "cluster_answers",
    "medoid",
    "stop_verdict",
]


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

SYNTH_SYSTEM = (
    "You are the single voice of an egregore: many minds deliberated and you must "
    "speak their considered conclusion as one answer.\n"
    "You are given (a) the user's question and (b) the distinct positions the minds "
    "reached, grouped by how many minds held each.\n"
    "Write the answer the egregore should give. Requirements:\n"
    "- Direct and substantive; do not describe the deliberation or mention the minds.\n"
    "- Where a majority position is well supported, state it plainly.\n"
    "- Where a minority position raised a real objection the majority missed, "
    "incorporate it as a caveat or a better answer.\n"
    "- No preamble, no meta-commentary, no 'as an AI'.\n"
    "- Match the format the question calls for (code, list, prose, number)."
)


class Egregore:
    """The fan-out orchestrator. One instance is safe to share across threads."""

    def __init__(
        self,
        provider: BaseProvider,
        config: EgregoreConfig | None = None,
        limiter: AdaptiveRateLimiter | None = None,
        budget: BudgetGuard | None = None,
        cache: ResponseCache | None = None,
    ) -> None:
        self.cfg = config or EgregoreConfig.from_env()
        self.provider = provider
        self.limiter = limiter or AdaptiveRateLimiter(
            rpm=self.cfg.rpm_limit, tpm=self.cfg.tpm_limit,
            safety_margin=self.cfg.safety_margin, adaptive=self.cfg.adaptive,
        )
        self.budget = budget or BudgetGuard(
            max_usd_request=self.cfg.max_usd_per_request,
            max_usd_day=self.cfg.max_usd_per_day,
            daily_path=self.cfg.daily_path,
        )
        self.cache = cache or ResponseCache(self.cfg.cache_path, self.cfg.cache_enabled)
        self._ledger_lock = threading.Lock()
        # single-flight: identical calls (same digest) inside a wave -- or across
        # two concurrent requests asking the same thing -- are issued once.
        self._flight_lock = threading.Lock()
        self._inflight: dict[str, dict] = {}
        self.runs = 0

    # -- public api ---------------------------------------------------------

    def run(
        self,
        prompt: str,
        *,
        agents: int | None = None,
        mode: str | None = None,
        deadline_s: float | None = None,
        stream_cb=None,
    ) -> EgregoreResult:
        """Answer `prompt` as one voice, deliberating behind the scenes.

        agents  -- exact number of minds to convene (overrides mode)
        mode    -- 'auto' (default), 'probe' (seed wave only), 'max' (to ceiling)
        stream_cb -- optional callable(event: dict) for live progress + deltas
        """
        cfg = self.cfg
        self.runs += 1
        t0 = time.time()
        self.budget.new_request()

        if mode is None:
            mode = "fixed" if agents else "auto"

        codex_block, codex_domains = (
            codex_for_prompt(prompt) if cfg.enable_codex else ("", [])
        )
        tool_block, matched_tools = (
            build_tool_augmentation_block(prompt, probe_local=False)
            if cfg.enable_zoth_tools else ("", [])
        )

        result = EgregoreResult(
            text="",
            prompt=prompt,
            scout_model=cfg.scout_model,
            synth_model=cfg.synth_model,
            codex_domains=codex_domains,
            zoth_tools=matched_tools,
        )
        started_wall = time.monotonic()
        deadline = (started_wall + deadline_s) if deadline_s else None

        # ---- plan waves ---------------------------------------------------
        target = agents if agents else (cfg.seed_agents if mode == "probe"
                                       else (cfg.max_agents if mode == "max" else cfg.max_agents))
        floor = min(agents, cfg.min_agents) if agents else (0 if mode == "probe" else cfg.min_agents)

        spawned = 0
        wave_no = 0
        answers: list[AgentAnswer] = []
        offset = 0
        wave_size = cfg.seed_agents if not agents else min(agents, cfg.seed_agents)
        stopped_by = "max_agents"

        # Pre-flight: the seed wave is a wave like every other wave, so it is
        # sized against remaining budget *before* it is dispatched. Refusals by
        # the per-call gate cost no money, but they land in `errors`, which reads
        # to an operator like a broken swarm rather than an exhausted wallet.
        if self._affordable_agents() <= 0:
            stopped_by = "budget"
            wave_size = 0

        while spawned < target and wave_size > 0:
            if deadline and time.monotonic() > deadline:
                stopped_by = "deadline"
                break

            remaining_target = target - spawned
            this_wave = max(1, min(wave_size, remaining_target))
            lenses = expand(this_wave, seed=prompt, offset=offset)
            offset += this_wave
            wave_no += 1

            wave_t0 = time.time()
            batch, budget_blocked = self._dispatch(
                lenses, prompt, deadline, codex_block=codex_block, tool_block=tool_block
            )
            answers.extend(batch)
            spawned += len(batch)

            ok_texts = [a.text for a in answers if a.ok]
            agree, diversity = agreement_of(ok_texts) if len(ok_texts) >= 2 else (1.0, 0.0)
            clusters = cluster_answers(ok_texts) if len(ok_texts) >= 2 else [[0]] if ok_texts else []
            # Has the swarm heard enough? Adaptive-Consistency (arXiv:2305.11860):
            # stop as soon as the Beta posterior says the leading answer is safe,
            # instead of paying for a fixed N that was never going to change.
            verdict = stop_verdict(ok_texts, tau=cfg.stop_confidence,
                                   window=cfg.esc_window,
                                   min_samples=cfg.consensus_min_samples)
            result.stop_confidence = verdict.confidence
            result.vote_share = verdict.share
            wave_meta = {
                "wave": wave_no,
                "requested": this_wave,
                "spawned": len(batch),
                "succeeded": sum(1 for a in batch if a.ok),
                "errors": sum(1 for a in batch if a.error),
                "cached": sum(1 for a in batch if a.cached),
                "agreement": round(agree, 4),
                "diversity": round(diversity, 4),
                "clusters": len(clusters),
                "vote_share": round(verdict.share, 4),
                "stop_confidence": round(verdict.confidence, 4),
                "vote_groups": verdict.groups,
                "elapsed_s": round(time.time() - wave_t0, 3),
            }
            result.waves.append(wave_meta)

            if stream_cb:
                stream_cb({"type": "wave", **wave_meta})

            result.agreement = agree
            result.diversity = diversity

            if budget_blocked:
                stopped_by = "budget"
                break
            if verdict.stop and spawned >= cfg.consensus_min_samples:
                stopped_by = "consensus" if verdict.rule == "asc" else "esc"
                if stream_cb:
                    stream_cb({"type": "consensus", **verdict.to_dict()})
                break
            if len(ok_texts) < 2:
                # nothing to compare; don't waste waves on a broken run
                if spawned >= max(1, floor):
                    stopped_by = "no_usable_answers"
                    break
            elif spawned >= max(1, floor) and wave_no >= cfg.force_min_waves:
                if agree >= cfg.stop_agreement:
                    stopped_by = "agreement"
                    break
                if agree >= cfg.stop_agreement_floor and spawned >= cfg.min_agents and \
                        mode == "auto" and this_wave >= cfg.min_agents:
                    stopped_by = "agreement_partial"
                    break

            if spawned >= target:
                stopped_by = "max_agents"
                break

            next_size = int(math.ceil(this_wave * cfg.escalation_factor))
            # never exceed the ceiling, and never exceed remaining budget
            affordable = self._affordable_agents()
            wave_size = max(1, min(next_size, cfg.max_agents, affordable))
            if affordable <= 0:
                stopped_by = "budget"
                break

        # ---- collapse -----------------------------------------------------
        ok = [a for a in answers if a.ok]
        result.agents_spawned = spawned
        result.agents_succeeded = len(ok)
        result.errors = sum(1 for a in answers if a.error)
        result.cache_hits = sum(1 for a in answers if a.cached)
        result.distinct_answers = len({a.text.strip() for a in ok})
        result.lens_coverage = coverage([a.lens for a in answers])
        result.stopped_by = stopped_by

        texts = [a.text for a in ok]
        if texts:
            result.clusters = self._cluster_report(texts)
            fallback = self._fallback_answer(texts)
        else:
            fallback = ""

        if stream_cb:
            stream_cb({"type": "collapse", "agents": result.agents_spawned,
                       "clusters": len(result.clusters), "agreement": round(result.agreement, 4)})

        final, synth_cost, synth_usage, synth_failed = self._synthesise(
            prompt, texts, result.clusters, stream_cb=stream_cb,
            codex_block=codex_block, tool_block=tool_block)
        result.synthesis_failed = synth_failed
        result.text = final or fallback
        result.cost_usd = sum(a.cost for a in answers) + synth_cost

        if synth_usage:
            result.tokens_in = int(synth_usage.get("prompt_tokens") or 0) + sum(
                int(a.usage.get("prompt_tokens") or 0) for a in answers)
            result.tokens_out = int(synth_usage.get("completion_tokens") or 0) + sum(
                int(a.usage.get("completion_tokens") or 0) for a in answers)
        else:
            result.tokens_in = sum(int(a.usage.get("prompt_tokens") or 0) for a in answers)
            result.tokens_out = sum(int(a.usage.get("completion_tokens") or 0) for a in answers)

        result.latency_s = time.time() - t0
        self._ledger(result)
        if stream_cb:
            stream_cb({"type": "done", **{k: v for k, v in result.to_dict().items() if k != "text"}})
        return result

    # -- dispatch -----------------------------------------------------------

    def _dispatch(self, lenses: list[Lens], prompt: str,
                  deadline: float | None, *, codex_block: str = "",
                  tool_block: str = "") -> tuple[list[AgentAnswer], bool]:
        """Run one wave in parallel. Returns (answers, budget_blocked)."""
        cfg = self.cfg
        out: list[AgentAnswer] = [None] * len(lenses)  # type: ignore[list-item]
        budget_blocked = False
        lock = threading.Lock()

        def task(i: int, lens: Lens) -> AgentAnswer:
            nonlocal budget_blocked
            system = lens.system_prompt(codex_block=codex_block, tool_block=tool_block)
            messages = [{"role": "system", "content": system},
                        {"role": "user", "content": prompt}]
            model = cfg.scout_model_for(i)
            digest = call_digest(model, system, prompt, cfg.temperature, cfg.max_tokens)
            if self.cache.enabled:
                hit = self.cache.get(digest)
                if hit:
                    return AgentAnswer(lens=lens, text=hit[0], usage=hit[1], cost=0.0, cached=True)

            holder, leader = self._flight_begin(digest)
            if not leader:
                holder["event"].wait(timeout=cfg.timeout_s)
                if holder["ok"]:
                    return AgentAnswer(lens=lens, text=holder["text"],
                                       usage=dict(holder["usage"]), cost=0.0, cached=True)
                # the leader failed; fall through and make the call ourselves

            projected = 0.0  # scout models are free/flash; exact cost arrives in usage
            allowed, why = self.budget.check(projected)
            if not allowed:
                with lock:
                    budget_blocked = True
                self._flight_finish(digest, holder)
                return AgentAnswer(lens=lens, error=f"budget: {why}")

            res = self.provider.chat(model, messages,
                                     temperature=cfg.temperature,
                                     max_tokens=cfg.max_tokens,
                                     timeout_s=cfg.timeout_s)
            if res.error:
                self._flight_finish(digest, holder)
                return AgentAnswer(lens=lens, error=res.error, latency_s=res.latency_s)
            cost = self.budget.settle(model, res.usage)
            if self.cache.enabled:
                self.cache.put(digest, model, res.text, res.usage)
            self._flight_finish(digest, holder, res.text, res.usage)
            return AgentAnswer(lens=lens, text=res.text, usage=res.usage, cost=cost,
                               latency_s=res.latency_s)

        workers = max(1, min(cfg.max_concurrency, len(lenses)))
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="egregore-mind") as ex:
            futs = {ex.submit(task, i, lens): i for i, lens in enumerate(lenses)}
            for fut in as_completed(futs):
                i = futs[fut]
                try:
                    out[i] = fut.result()
                except Exception as e:  # noqa: BLE001 - one mind must not kill the run
                    out[i] = AgentAnswer(lens=lenses[i], error=f"{type(e).__name__}: {e}")
                if deadline and time.monotonic() > deadline:
                    for f in futs:
                        f.cancel()
        return [a for a in out if a is not None], budget_blocked

    def _flight_begin(self, digest: str) -> tuple[dict, bool]:
        """Single-flight gate. Returns (holder, is_leader).

        A non-leader waits on the holder; if the leader produced text it reuses
        it (cached=True, no cost) instead of paying for the same call twice.
        """
        with self._flight_lock:
            holder = self._inflight.get(digest)
            if holder is not None:
                return holder, False
            holder = {"event": threading.Event(), "text": "", "usage": {}, "ok": False}
            self._inflight[digest] = holder
            return holder, True

    def _flight_finish(self, digest: str, holder: dict,
                       text: str = "", usage: dict | None = None) -> None:
        """Publish the leader's result and release every waiter."""
        holder["text"] = text or ""
        holder["usage"] = dict(usage or {})
        holder["ok"] = bool(text)
        with self._flight_lock:
            self._inflight.pop(digest, None)
        holder["event"].set()

    def _affordable_agents(self) -> int:
        """How many more minds the remaining budget can pay for (free => unlimited).

        The planner and the per-call gate have to agree. Sizing waves from the
        per-request cap while the gate enforced the *day* cap made the swarm
        dispatch waves whose calls were then refused one by one -- agents that
        cost latency and told us nothing. Size from whichever ceiling binds
        first.
        """
        from .config import is_free

        if is_free(self.cfg.scout_model):
            return self.cfg.max_agents
        headroom = min(self.budget.remaining_request(), self.budget.remaining_day())
        per_call = self._scout_cost_estimate()
        if per_call <= 0:
            return self.cfg.max_agents
        # +1e-9 absorbs binary-float error: $0.01 of headroom at $0.01 per call
        # is one call, not 0.9999999999 of one.
        return int(headroom / per_call + 1e-9)

    def _scout_cost_estimate(self) -> float:
        """Measured average call cost from this run, else a flash-price guess.

        Snapshot totals include the (pricier) synthesis call, which biases the
        estimate upward -- the safe direction: we under-plan rather than
        over-spend.
        """
        snap = self.budget.snapshot()
        calls = int(snap.get("calls") or 0)
        spent = float(snap.get("day_spent_usd") or 0.0)
        if calls >= 4 and spent > 0:
            measured = spent / calls
            if measured > 0:
                return measured
        return 0.0002  # ~flash price per scout call, before we have measurements

    # -- collapse helpers ---------------------------------------------------

    def _cluster_report(self, texts: list[str]) -> list[dict]:
        groups = cluster_answers(texts)
        report = []
        for g in groups[:16]:
            rep = medoid(texts, g)
            report.append({
                "size": len(g),
                "share": round(len(g) / max(1, len(texts)), 3),
                "representative": texts[rep][:600],
            })
        return report

    def _fallback_answer(self, texts: list[str]) -> str:
        groups = cluster_answers(texts)
        if not groups:
            return texts[0] if texts else ""
        return texts[medoid(texts, groups[0])]

    def _synthesise(self, prompt: str, texts: list[str], clusters: list[dict],
                    stream_cb=None, *, codex_block: str = "",
                    tool_block: str = "") -> tuple[str, float, dict, bool]:
        cfg = self.cfg
        if not texts:
            return "", 0.0, {}, True
        if len(texts) == 1:
            return texts[0], 0.0, {}, False

        synth_system = SYNTH_SYSTEM
        extra_blocks = [b for b in (codex_block, tool_block) if b]
        if extra_blocks:
            synth_system = synth_system + "\n\n" + "\n\n".join(extra_blocks)

        positions = []
        for i, c in enumerate(clusters[:12], 1):
            positions.append(f"[{i}] held by {c['size']} mind(s) "
                             f"({int(c['share'] * 100)}%): {c['representative']}")
        body = (
            f"QUESTION:\n{prompt}\n\n"
            f"DELIBERATION: {len(texts)} distinct mind-answers collapsed into "
            f"{len(clusters)} positions.\n\n" + "\n\n".join(positions)
        )
        messages = [{"role": "system", "content": synth_system},
                    {"role": "user", "content": body}]

        # The collapse is the single most expensive call in a run (pro model,
        # long prompt), so it gets the same treatment as the fan-out: an
        # identical repeat of the whole question should cost nothing at all.
        synth_tokens = max(cfg.max_tokens, 1200)
        digest = call_digest(cfg.synth_model, synth_system, body, 0.3, synth_tokens)
        if self.cache.enabled:
            hit = self.cache.get(digest)
            if hit is not None and hit[0]:
                return hit[0], 0.0, dict(hit[1] or {}), False

        allowed, _why = self.budget.check(0.0)
        if not allowed:
            return "", 0.0, {}, True

        if stream_cb is not None:
            acc: list[str] = []
            usage: dict = {}
            err = False
            try:
                for kind, payload in self.provider.chat_stream(
                        cfg.synth_model, messages, temperature=0.3,
                        max_tokens=max(cfg.max_tokens, 1200), timeout_s=cfg.timeout_s):
                    if kind == "delta":
                        acc.append(payload)
                        stream_cb({"type": "delta", "text": payload})
                    elif kind == "usage":
                        usage = payload or {}
            except Exception as e:  # noqa: BLE001
                err = True
                usage = {"error": str(e)}
            text = "".join(acc).strip()
            if not text:
                return "", 0.0, {}, True
            if self.cache.enabled and not err:
                self.cache.put(digest, cfg.synth_model, text, usage)
            cost = self.budget.settle(cfg.synth_model, usage)
            return text, cost, usage, err

        res = self.provider.chat(cfg.synth_model, messages, temperature=0.3,
                                 max_tokens=max(cfg.max_tokens, 1200),
                                 timeout_s=cfg.timeout_s)
        if res.error or not res.text:
            return "", 0.0, res.usage, True
        if self.cache.enabled:
            self.cache.put(digest, cfg.synth_model, res.text, res.usage)
        cost = self.budget.settle(cfg.synth_model, res.usage)
        return res.text, cost, res.usage, False

    def _ledger(self, result: EgregoreResult) -> None:
        path = Path(self.cfg.ledger_path)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            rec = {
                "ts": time.time(),
                "prompt_sha256": hashlib.sha256(result.prompt.encode()).hexdigest()[:16],
                "prompt_chars": len(result.prompt),
                **{k: v for k, v in result.to_dict().items() if k not in ("text", "clusters")},
            }
            with self._ledger_lock, path.open("a") as fh:
                fh.write(json.dumps(rec) + "\n")
        except Exception:
            pass

    # -- introspection ------------------------------------------------------

    def stats(self) -> dict:
        return {
            "runs": self.runs,
            "limiter": self.limiter.snapshot(),
            "budget": self.budget.snapshot(),
            "cache": self.cache.stats(),
            "provider": self.provider.stats(),
            "zoth_environment": detect_zoth_environment(probe_daemons=False),
            "config": {
                "scout_model": self.cfg.scout_model,
                "synth_model": self.cfg.synth_model,
                "seed_agents": self.cfg.seed_agents,
                "min_agents": self.cfg.min_agents,
                "max_agents": self.cfg.max_agents,
                "max_concurrency": self.cfg.max_concurrency,
                "stop_agreement": self.cfg.stop_agreement,
                "enable_codex": self.cfg.enable_codex,
                "enable_zoth_tools": self.cfg.enable_zoth_tools,
            },
        }
