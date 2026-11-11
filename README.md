# EGREGORE (`zoth-egregore` · `:8147`) ![Status: Beta](https://img.shields.io/badge/status-experimental%20beta-ffb454?style=flat-square) ![Version: 0.1.0-beta](https://img.shields.io/badge/version-0.1.0--beta-4be3c1?style=flat-square)

> **One OpenAI-compatible model face (`POST /v1/chat/completions`), backed by 3,456 co-prime DeepSeek Flash × Nous Hermes minds, a distilled Design-Director & Formal-Logic Codex, and native 77-tool ZothOS / Zoth Studio orchestration.**
>
> **Dedicated Website & Live Workbench**: [https://zoth-egregore.netlify.app](https://zoth-egregore.netlify.app) • Engineered by **1nc0gn30** (`@1nc0gn30`) • [NullAI Platform](https://nullai.tech)

> [!NOTE]
> **Experimental Beta (`v0.1.0-beta`)** — Research-grade deliberative AI model & agent engine powered by **DeepSeek Flash (`deepseek/deepseek-v4.1-flash`)** via **Nous Hermes Agent** (`~/.hermes/auth.json` / `NOUS_API_KEY` / `DEEPSEEK_API_KEY`) and verified under `61/61` deterministic unit tests.
> - **Expanded Adversarial Tests**: Coming Soon
> - **Public Multi-Domain Benchmarks**: Coming Soon
> - **HuggingFace Weights & Trace Datasets**: Coming Soon

---

## What It Does

`zoth-egregore` turns ultra-fast **DeepSeek Flash** scouts routed through **Nous Hermes** (plus a `deepseek/deepseek-v4-pro` collapse pass) into an adaptive collective intelligence of **8 to 1,000 minds** behind a zero-dependency Python 3.10+ stdlib server on `http://127.0.0.1:8147/v1`.

Any OpenAI client (Nous Hermes Agent, Python `openai` SDK, Cursor, Cline, `curl`, Zoth Studio) selects deliberation depth purely through the `model` string:

| Model String | Deliberation Mode | Behavior |
|---|---|---|
| `zoth-egregore` | **Adaptive (`auto`)** | 8-mind co-prime seed probe; escalates in waves (`×3.0`) only while disagreement persists; stops the instant Beta posterior $P(\text{leader}) \ge 0.95$. |
| `zoth-egregore:probe` | **Fast Probe** | Single 8-mind co-prime wave + synthesis collapse. |
| `zoth-egregore:50` | **Fixed 50 Minds** | Convene exactly 50 distinct orthogonal lenses. |
| `zoth-egregore:256` | **Fixed 256 Minds** | Convene 256 distinct orthogonal lenses. |
| `zoth-egregore:1000` | **Full Congress** | Convene 1,000 distinct orthogonal lenses under adaptive RPM/TPM pacing. |
| `zoth-egregore:max` | **Max Escalation** | Escalates up to `max_agents` if disagreement holds. |

---

## Architecture & Mathematical Foundations

1. **DeepSeek Flash × Nous Hermes Self-MoA (`arXiv:2502.00674`)**: Sampling diverse cognitive lenses over a strong fast scout model (`deepseek/deepseek-v4.1-flash`) outperforms mixing weaker heterogeneous models. Diversity comes from the **3,456-Lens Co-Prime Pantheon** (`24 Archetypes × 18 Domains × 8 Stances`), traversed via SHA-256 stride coprime to $3456 = 2^7 \cdot 3^3$ ($\gcd(\text{stride}, 3456) = 1$) so every single mind up to 3,456 is collision-free.
2. **Adaptive-Consistency (`arXiv:2305.11860`) & ESC (`arXiv:2401.10480`)**: Evaluates $P(p_1 > p_2 \mid V_1, V_2) = 1 - I_{0.5}(V_1+1, V_2+1) \ge 0.95$ via Lentz continued fractions (`betai`) with zero judge calls—cutting sample spend by up to `7.9×` on clear consensus while escalating only on real disagreement.
3. **Free-MAD Medoid Fallback (`arXiv:2509.11035`)**: Single-round independent exploration + cluster-medoid synthesis prevents sycophantic multi-round drift and guarantees non-crashing medoid fallback if synthesis fails.
4. **Distilled Design-Director & Formal-Logic Codex (`egregore/codex.py`)**: Arms scout minds and the synthesis collapse with formal deductive invariants (necessary vs sufficient conditions, boundary proofs, counterexample search), 8pt/APCA UI design judgment, 60fps GPU motion tokens, and Ring-3 security invariants.
5. **Native Zoth 77-Tool & Daemon Orchestrator (`egregore/zoth_tools.py`)**: Automatically detects [ZothOS](https://zothos.nullai.tech) and [Zoth Studio](https://zoth.nullai.tech) environments, routing across local CLI binaries and 23 loopback daemons (`Neuro-Memory :8094` Hebbian STDP recall, `Adytum :8135` DAG planner, `Swarm Multiplexer :8141`, `WCAG Contrast Guard :8150`, `Reality Shader Forge :8118`, `HexStrike :8138`, `Zoth-Relay :8765`).
6. **Header-Driven `AdaptiveRateLimiter` & Pre-Flight `BudgetGuard`**: Tracks `x-ratelimit-remaining-*` wire headers (`400 RPM / 4M TPM`), enforces per-request and rolling daily USD caps *before* wave dispatch, and deduplicates concurrent identical calls via single-flight + SQLite WAL caching.

---

## Quickstart & ZothOS CLI Commands

```bash
# Inspect local ZothOS / Zoth Studio 77-tool arsenal & active Design+Logic canons
zoth-egregore tools "Design a dark mode UI with WCAG contrast and memory recall" --probe

# Offline benchmark (agreeing vs disagreeing swarm escalation)
zoth-egregore bench

# Inspect co-prime Pantheon × Domain × Stance lenses
zoth-egregore lenses -n 12

# Run one deliberation from the terminal
zoth-egregore run "What breaks first in distributed consensus under asymmetric packet loss?" --mock --json

# Launch the OpenAI-compatible server + dashboard on http://127.0.0.1:8147
zoth-egregore serve --port 8147

# Run full pytest suite (61 tests)
pytest -q
```

---

## Validation & Open-Science Roadmap

- **Tests — Coming Soon**: Expanded live-wire adversarial, red-team, and multi-turn stress test suites (61 offline orchestrator assertions active in `tests/` today).
- **Benchmarks — Coming Soon**: Reproducible evaluations across GPQA-Diamond, LiveCodeBench, SWE-bench Verified, AlpacaEval 2.0, and blind Design Rubrics.
- **HuggingFace — Coming Soon**: Open deliberation consensus traces, Design+Logic preference datasets, and distilled adapters on HuggingFace Hub.

---

## Support Open-Access Engineering

100% free and open-access (MIT). Optional support:
- ☕ **Buy Us a Coffee**: https://buy.stripe.com/3cIfZg27PdKo2D64Ocfw40X
- **Solana Tip**: `GG2eQbVh8ut1BK6j1A2tz7pSySdLpD38BgyEhGcxdXoK`

Engineered by **1nc0gn30** (`@1nc0gn30`) • [1nc0gn30.si](https://1nc0gn30.si) • [nullai.tech](https://nullai.tech) • [ZothOS](https://zothos.nullai.tech) • [Zoth Studio](https://zoth.nullai.tech)
