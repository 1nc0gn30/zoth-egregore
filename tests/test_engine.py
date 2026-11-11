"""The engine's three claims, tested offline against MockProvider.

  * cheapness      -- a unanimous task costs a seed wave plus one synthesis call
  * escalation     -- disagreement is what earns more agents
  * never worse    -- synthesis failure still returns a real answer
  * rate-limit safety -- identical in-flight calls are issued once (single-flight)

MockProvider is deterministic and touches no network, so a failure here is a bug
in the orchestrator, never the wire.
"""

from __future__ import annotations

import hashlib
from concurrent.futures import ThreadPoolExecutor

import pytest

from egregore.config import EgregoreConfig
from egregore.engine import Egregore
from egregore.providers import MockProvider

CONSTANT = "The socket is never closed before the retry loop starts, so the third retry leaks."


def _cfg(tmp_path, **over):
    cfg = EgregoreConfig.from_env(
        cache_path=tmp_path / "cache.sqlite3",
        ledger_path=tmp_path / "ledger.jsonl",
        daily_path=tmp_path / "daily.json",
        cache_enabled=False,
    )
    for k, v in over.items():
        setattr(cfg, k, v)
    return cfg


def _const_responder(model, messages):
    """Every mind says the same thing -> unanimous by construction."""
    return CONSTANT


def _distinct_responder(model, messages):
    """Every mind says something provably unique -> permanent disagreement.

    A hex digest shares no tokens with any other digest, so similarity is 0 and
    no vote group can ever merge two of them.
    """
    system = messages[0].get("content", "") if messages else ""
    return hashlib.sha256(system.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Cheapness
# ---------------------------------------------------------------------------


def test_unanimous_task_stops_cheap(tmp_path):
    provider = MockProvider(responder=_const_responder)
    eng = Egregore(provider, _cfg(tmp_path))
    res = eng.run("why does the deploy fail?")

    assert res.stopped_by == "consensus"
    assert res.agents_spawned == 8          # one seed wave, no escalation
    assert res.agents_succeeded == 8
    assert res.vote_share == pytest.approx(1.0)
    assert res.stop_confidence > 0.95
    assert len(provider.calls) == 9         # 8 minds + 1 synthesis, not 1000
    assert res.text.strip()


def test_probe_mode_is_a_single_seed_wave(tmp_path):
    provider = MockProvider(responder=_distinct_responder)
    eng = Egregore(provider, _cfg(tmp_path))
    res = eng.run("anything", mode="probe")
    assert res.agents_spawned == 8
    assert len(provider.calls) == 9


# ---------------------------------------------------------------------------
# Escalation
# ---------------------------------------------------------------------------


def test_disagreement_escalates_to_the_ceiling(tmp_path):
    cfg = _cfg(
        tmp_path,
        max_agents=32,
        min_agents=8,
        seed_agents=8,
        escalation_factor=3.0,
        stop_agreement=1.01,        # never satisfied
        stop_agreement_floor=1.01,
        stop_confidence=1.01,       # posterior can never fire
        esc_window=1000,
    )
    provider = MockProvider(responder=_distinct_responder)
    eng = Egregore(provider, cfg)
    res = eng.run("a genuinely hard question")

    assert res.stopped_by == "max_agents"
    assert res.agents_spawned == 32          # 8 then 24
    assert [w["spawned"] for w in res.waves] == [8, 24]
    assert res.agreement < 0.2               # nothing lined up
    assert len(provider.calls) == 33         # 32 minds + synthesis


def test_escalation_respects_max_agents(tmp_path):
    cfg = _cfg(tmp_path, max_agents=13, min_agents=8, seed_agents=8,
               stop_agreement=1.01, stop_agreement_floor=1.01,
               stop_confidence=1.01, esc_window=1000)
    provider = MockProvider(responder=_distinct_responder)
    res = Egregore(provider, cfg).run("hard")
    assert res.agents_spawned == 13
    assert res.waves[-1]["spawned"] == 5


def test_agreement_stops_escalation_above_min_agents(tmp_path):
    cfg = _cfg(tmp_path, max_agents=200, min_agents=50, seed_agents=8,
               escalation_factor=3.0, stop_confidence=1.01, esc_window=1000)
    provider = MockProvider(responder=_const_responder)
    eng = Egregore(provider, cfg)
    res = eng.run("agreed question")
    # consensus stop fires first here, at the seed wave
    assert res.stopped_by in ("consensus", "agreement")


# ---------------------------------------------------------------------------
# Never worse than one model
# ---------------------------------------------------------------------------


def test_synthesis_failure_falls_back_to_a_medoid_answer(tmp_path):
    def responder(model, messages):
        body = messages[-1].get("content", "")
        if "DELIBERATION:" in body:
            return ""                      # the collapse call dies
        return CONSTANT

    provider = MockProvider(responder=responder)
    eng = Egregore(provider, _cfg(tmp_path))
    res = eng.run("what broke?")
    assert res.synthesis_failed is True
    assert res.text.strip() == CONSTANT    # still a real answer, not empty


def test_all_minds_failing_yields_an_error_not_a_crash(tmp_path):
    provider = MockProvider(fail_429_times=10_000)
    cfg = _cfg(tmp_path, max_agents=8, min_agents=8, seed_agents=8, esc_window=1000)
    res = Egregore(provider, cfg).run("anything")
    assert res.agents_succeeded == 0
    assert res.errors >= 8
    assert res.text == ""
    assert res.stopped_by in ("no_usable_answers", "max_agents", "budget")


# ---------------------------------------------------------------------------
# Single-flight: identical in-flight calls are issued once
# ---------------------------------------------------------------------------


def test_concurrent_identical_requests_share_one_wave(tmp_path):
    cfg = _cfg(tmp_path, cache_enabled=False)      # only single-flight can help here
    provider = MockProvider(responder=_const_responder, latency_s=0.15)
    eng = Egregore(provider, cfg)

    with ThreadPoolExecutor(max_workers=2) as ex:
        a = ex.submit(eng.run, "same question, twice")
        b = ex.submit(eng.run, "same question, twice")
        ra, rb = a.result(), b.result()

    assert ra.text.strip() and rb.text.strip()
    # Two runs would be 16 minds + 2 collapses = 18 calls without coalescing.
    assert len(provider.calls) < 18


def test_cached_calls_are_not_billed_twice(tmp_path):
    cfg = _cfg(tmp_path, cache_enabled=True, max_agents=8, min_agents=8, esc_window=1000,
               stop_confidence=1.01, stop_agreement=1.01, stop_agreement_floor=1.01)
    provider = MockProvider(responder=_distinct_responder)
    eng = Egregore(provider, cfg)
    eng.run("repeated question")
    first = len(provider.calls)
    res2 = eng.run("repeated question")
    assert len(provider.calls) == first          # everything came from cache
    assert res2.cache_hits >= 1


# ---------------------------------------------------------------------------
# Budget
# ---------------------------------------------------------------------------


def test_budget_day_ceiling_stops_the_swarm(tmp_path):
    """The day cap must bind before the swarm spends anything like the request cap.

    Regression: the planner sized waves from the per-request ceiling while the
    per-call gate enforced the day ceiling, so a run against a near-zero day
    budget still dispatched waves of calls that were refused one at a time.
    """
    # Case A: $0.08 day ceiling (with $0.50 per-request ceiling) pays for the 8-mind
    # seed wave ($0.08) cleanly with 0 refused calls, then halts before wave 2.
    cfg = _cfg(tmp_path, max_agents=1000, min_agents=8, seed_agents=8,
               scout_model="deepseek/deepseek-v4.1-flash",   # not free -> costs money
               max_usd_per_day=0.08, stop_confidence=1.01, esc_window=1000,
               stop_agreement=1.01, stop_agreement_floor=1.01,
               force_min_waves=False)
    provider = MockProvider(responder=_distinct_responder, cost_per_call=0.01)
    res = Egregore(provider, cfg).run("expensive question")

    assert res.stopped_by == "budget"
    assert res.agents_spawned == 8            # the seed wave, then nothing
    assert res.errors == 0                    # nothing was spent and then refused


def test_budget_sub_call_day_ceiling_halts_preflight(tmp_path):
    """When remaining day budget cannot afford even one scout call, pre-flight halts cleanly."""
    cfg = _cfg(tmp_path, max_agents=1000, min_agents=8, seed_agents=8,
               scout_model="deepseek/deepseek-v4.1-flash",
               max_usd_per_day=0.00005, stop_confidence=1.01, esc_window=1000,
               stop_agreement=1.01, stop_agreement_floor=1.01,
               force_min_waves=False)
    provider = MockProvider(responder=_distinct_responder, cost_per_call=0.01)
    res = Egregore(provider, cfg).run("expensive question")

    assert res.stopped_by == "budget"
    assert res.agents_spawned == 0
    assert res.errors == 0


def test_day_ceiling_sizes_the_final_wave_instead_of_refusing_calls(tmp_path):
    """A partly-spent day budget buys a proportional wave, not a refused one."""
    cfg = _cfg(tmp_path, max_agents=1000, min_agents=4, seed_agents=4,
               escalation_factor=2.0, scout_model="deepseek/deepseek-v4.1-flash",
               max_usd_per_day=0.05, cache_enabled=False,
               stop_confidence=1.01, esc_window=1000,
               stop_agreement=1.01, stop_agreement_floor=1.01,
               force_min_waves=False)
    provider = MockProvider(responder=_distinct_responder, cost_per_call=0.01)
    res = Egregore(provider, cfg).run("expensive question")

    # 4 minds ($0.04) + exactly one affordable mind ($0.01) = $0.05 of a $0.05 day
    assert res.agents_spawned == 5
    assert res.errors == 0
    assert res.stopped_by == "budget"
    assert provider.stats()["calls"] == 6     # 5 minds + the collapse


def test_env_vars_name_the_budget_ceilings(tmp_path, monkeypatch):
    """Ops sets these by name; a rename here is a silent spending bug."""
    monkeypatch.setenv("EGREGORE_MAX_USD_DAY", "0.25")
    monkeypatch.setenv("EGREGORE_MAX_USD_REQUEST", "0.05")
    cfg = EgregoreConfig.from_env(cache_path=tmp_path / "c.sqlite3",
                                  daily_path=tmp_path / "d.json")
    assert cfg.max_usd_per_day == 0.25
    assert cfg.max_usd_per_request == 0.05


# ---------------------------------------------------------------------------
# Config / model choice
# ---------------------------------------------------------------------------


def test_default_scout_is_one_model(tmp_path):
    cfg = _cfg(tmp_path)
    assert cfg.scout_pool == []
    assert cfg.scout_model_for(0) == cfg.scout_model_for(99) == cfg.scout_model


def test_optional_scout_pool_rotates(tmp_path):
    cfg = _cfg(tmp_path, scout_pool=["a/model", "b/model"])
    assert [cfg.scout_model_for(i) for i in range(4)] == ["a/model", "b/model", "a/model", "b/model"]


def test_from_env_ignores_none_overrides():
    cfg = EgregoreConfig.from_env(scout_model=None, synth_model=None, port=None)
    assert cfg.scout_model
    assert cfg.synth_model
    assert cfg.port == 8147


def test_all_3456_lens_signatures_are_collision_free():
    from egregore.lenses import PRODUCT_SIZE, lens_at
    sigs = {lens_at(i).signature for i in range(PRODUCT_SIZE)}
    assert PRODUCT_SIZE == 3456
    assert len(sigs) == 3456


def test_stats_expose_limiter_budget_and_cache(tmp_path):
    eng = Egregore(MockProvider(responder=_const_responder), _cfg(tmp_path))
    eng.run("hello")
    st = eng.stats()
    assert st["runs"] == 1
    for key in ("limiter", "budget", "cache", "provider", "config"):
        assert key in st
