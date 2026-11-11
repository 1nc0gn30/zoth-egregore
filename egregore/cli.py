"""Command line for EGREGORE.

    python -m egregore serve                 # the model face on :8147
    python -m egregore run "question" -n 64  # one deliberation, printed
    python -m egregore bench                 # offline: prove the swarm works
    python -m egregore selftest              # live: 1 real call to the provider
    python -m egregore lenses -n 12          # show the minds
    python -m egregore stats                 # limiter + budget + cache
"""

from __future__ import annotations

import argparse
import json
import sys
import time

from .config import EgregoreConfig
from .lenses import coverage, expand
from .providers import MockProvider, OpenAICompatProvider


def _engine(cfg: EgregoreConfig, mock: bool = False):
    """Build the engine. One limiter/budget/cache is shared by provider and engine,
    so the rate limiter that governs the wire is the one `stats` reports."""
    from .budget import BudgetGuard
    from .cache import ResponseCache
    from .engine import Egregore
    from .ratelimit import AdaptiveRateLimiter

    limiter = AdaptiveRateLimiter(rpm=cfg.rpm_limit, tpm=cfg.tpm_limit,
                                  safety_margin=cfg.safety_margin, adaptive=cfg.adaptive)
    budget = BudgetGuard(max_usd_request=cfg.max_usd_per_request,
                         max_usd_day=cfg.max_usd_per_day, daily_path=cfg.daily_path)
    cache = ResponseCache(cfg.cache_path, cfg.cache_enabled)
    if mock:
        provider = MockProvider()
    else:
        provider = OpenAICompatProvider(cfg.base_url, cfg.api_key, limiter=limiter)
    return Egregore(provider, cfg, limiter=limiter, budget=budget, cache=cache)


def cmd_serve(args) -> int:
    cfg = EgregoreConfig.from_env(port=args.port, max_agents=args.max_agents,
                                 scout_model=args.scout, synth_model=args.synth)
    problems = cfg.validate()
    if problems:
        print("EGREGORE cannot start:", file=sys.stderr)
        for p in problems:
            print("  -", p, file=sys.stderr)
        return 2
    from .server import EgregoreServer

    engine = _engine(cfg)
    server = EgregoreServer(engine, cfg)
    print(f"EGREGORE face listening on http://127.0.0.1:{cfg.port}/v1  "
          f"(model: {cfg.model_id}, {cfg.min_agents}-{cfg.max_agents} minds)")
    print(f"  scout={cfg.scout_model}  synth={cfg.synth_model}")
    try:
        server.serve_forever(host=args.host, port=cfg.port)
    except KeyboardInterrupt:
        print("\nstopping")
    return 0


def cmd_run(args) -> int:
    cfg = EgregoreConfig.from_env(scout_model=args.scout, synth_model=args.synth)
    engine = _engine(cfg, mock=args.mock)
    t0 = time.time()
    res = engine.run(args.prompt, agents=args.agents, mode=args.mode)
    if args.json:
        print(json.dumps(res.to_dict(), indent=2))
        return 0
    print(res.text)
    print("\n" + "-" * 68, file=sys.stderr)
    print(f"minds={res.agents_spawned} ok={res.agents_succeeded} clusters={len(res.clusters)} "
          f"agreement={res.agreement:.3f} stopped_by={res.stopped_by} "
          f"cost=${res.cost_usd:.6f} latency={time.time()-t0:.2f}s", file=sys.stderr)
    for w in res.waves:
        print(f"  wave {w['wave']}: {w['spawned']} minds, agreement {w['agreement']:.3f}, "
              f"{w['clusters']} clusters, {w['elapsed_s']:.2f}s, {w['errors']} errors", file=sys.stderr)
    return 0


def cmd_bench(args) -> int:
    """Offline benchmark: the same policy the live engine uses, but no network."""
    import hashlib
    from .engine import Egregore

    cfg = EgregoreConfig.from_env(max_agents=args.max_agents, seed_agents=args.seed,
                                  min_agents=args.min_agents, cache_enabled=False)

    def agreeing(model, messages):
        return "The answer is 42 and it is certainly the answer to everything here."

    def disagreeing(model, messages):
        system = messages[0]["content"]
        h = hashlib.sha256(system.encode()).hexdigest()
        toks = [f"hyp{h[j:j+6]}" for j in range(0, 48, 6)]
        return " ".join(toks)

    print(f"bench: seed={cfg.seed_agents} min={cfg.min_agents} max={cfg.max_agents} "
          f"stop_agreement={cfg.stop_agreement} factor={cfg.escalation_factor}")
    for label, responder in (("agreeing swarm", agreeing), ("disagreeing swarm", disagreeing)):
        cfg2 = EgregoreConfig.from_env(max_agents=args.max_agents, seed_agents=args.seed,
                                       min_agents=args.min_agents, cache_enabled=False)
        eng = Egregore(MockProvider(responder=responder), cfg2)
        t0 = time.time()
        res = eng.run("What is the answer?", mode="auto")
        print(f"  {label:18s} minds={res.agents_spawned:4d} waves={len(res.waves)} "
              f"agreement={res.agreement:.3f} clusters={len(res.clusters):3d} "
              f"stopped_by={res.stopped_by:20s} {time.time()-t0:.2f}s")
    return 0


def cmd_selftest(args) -> int:
    """One real, tiny call against the configured provider to prove the wire works."""
    cfg = EgregoreConfig.from_env()
    problems = cfg.validate()
    if problems:
        for p in problems:
            print("  -", p, file=sys.stderr)
        return 2
    from .providers import OpenAICompatProvider

    prov = OpenAICompatProvider(cfg.base_url, cfg.api_key)
    t0 = time.time()
    res = prov.chat(cfg.scout_model, [{"role": "user", "content": "Reply with exactly: OK"}],
                    max_tokens=8)
    print(f"provider : {cfg.base_url}")
    print(f"model    : {cfg.scout_model}")
    print(f"latency  : {time.time()-t0:.2f}s")
    if res.error:
        print(f"FAILED   : {res.error}")
        return 1
    print(f"reply    : {res.text[:60]!r}")
    print(f"usage    : {json.dumps(res.usage)}")
    print("provider wire OK")
    return 0


def cmd_lenses(args) -> int:
    lenses = expand(args.n, seed=args.seed)
    for l in lenses:
        print(f"{l.index:4d}  {l.signature:34s}  {l.domain}")
    print(f"\ncoverage: {coverage(lenses)}")
    return 0


def cmd_stats(args) -> int:
    if args.state_dir:
        from pathlib import Path

        base = Path(args.state_dir)
        cfg = EgregoreConfig.from_env(cache_path=base / "cache.sqlite3",
                                      ledger_path=base / "ledger.jsonl",
                                      daily_path=base / "daily.json")
    else:
        cfg = EgregoreConfig.from_env()
    eng = _engine(cfg)
    print(json.dumps(eng.stats(), indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="egregore", description="EGREGORE — one model, many minds")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("serve", help="run the OpenAI-compatible model face")
    s.add_argument("--port", type=int, default=8147)
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--max-agents", type=int, default=1000)
    s.add_argument("--scout", default=None)
    s.add_argument("--synth", default=None)
    s.set_defaults(fn=cmd_serve)

    r = sub.add_parser("run", help="one deliberation")
    r.add_argument("prompt")
    r.add_argument("-n", "--agents", type=int, default=None)
    r.add_argument("--mode", default=None, choices=[None, "auto", "probe", "max", "fixed"])
    r.add_argument("--json", action="store_true")
    r.add_argument("--mock", action="store_true", help="offline, deterministic")
    r.add_argument("--scout", default=None)
    r.add_argument("--synth", default=None)
    r.set_defaults(fn=cmd_run)

    b = sub.add_parser("bench", help="offline swarm-policy benchmark")
    b.add_argument("--max-agents", type=int, default=400)
    b.add_argument("--seed", type=int, default=8)
    b.add_argument("--min-agents", type=int, default=50)
    b.set_defaults(fn=cmd_bench)

    st = sub.add_parser("selftest", help="one real provider call")
    st.set_defaults(fn=cmd_selftest)

    ln = sub.add_parser("lenses", help="show the minds")
    ln.add_argument("-n", type=int, default=12)
    ln.add_argument("--seed", default="egregore")
    ln.set_defaults(fn=cmd_lenses)

    sx = sub.add_parser("stats", help="limiter, budget, cache")
    sx.add_argument("--state-dir", default=None)
    sx.set_defaults(fn=cmd_stats)

    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
