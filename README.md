# Zoth Egregore (`zoth-egregore` · `:8147`) ![Status: Beta](https://img.shields.io/badge/status-experimental%20beta-ffb454?style=flat-square) ![Version: 0.1.0-beta](https://img.shields.io/badge/version-0.1.0--beta-4be3c1?style=flat-square)

> **One OpenAI-compatible model face (`POST /v1/chat/completions`), backed by up to 1,000 structured Pantheon minds.**
> Engineered via Nous Hermes Agent × 1nc0gn30 (`@1nc0gn30`) • [NullAI Platform](https://nullai.tech)

> [!NOTE]
> **Experimental Beta (`v0.1.0-beta`)** — Research-grade collective-intelligence proxy generated via Nous Hermes Agent and hardened under the Zoth test gate (`54/54` tests passing). Interfaces, escalation heuristics, and lens weights may evolve between minor releases.

---

## What It Does

`zoth-egregore` turns a single fast OpenAI-compatible model (default free/flash scout models on Nous Portal or OpenRouter + one synthesis pass) into an adaptive collective intelligence of **8 to 1,000 minds** exposed behind a zero-dependency stdlib server on `http://127.0.0.1:8147/v1`.

Any OpenAI client (Hermes Agent, Cursor, Cline, `curl`, Zoth Studio) selects deliberation depth purely through the `model` string:

| Model String | Deliberation Mode | Behavior |
|---|---|---|
| `zoth-egregore` | **Adaptive (`auto`)** | 8-mind co-prime seed probe; escalates in waves (`×3.0`) only while disagreement persists; stops the instant Beta posterior $P(\text{leader}) \ge 0.95$. |
| `zoth-egregore:probe` | **Fast Probe** | Single 8-mind co-prime wave + synthesis collapse. |
| `zoth-egregore:50` | **Fixed 50 Minds** | Convene exactly 50 distinct orthogonal lenses. |
| `zoth-egregore:256` | **Fixed 256 Minds** | Convene 256 distinct orthogonal lenses. |
| `zoth-egregore:1000` | **Full Congress** | Convene 1,000 distinct orthogonal lenses under adaptive RPM/TPM pacing. |
| `zoth-egregore:max` | **Max Escalation** | Escalates up to `max_agents` if disagreement holds. |

---

## Research & Mathematical Foundations

1. **Self-MoA (`arXiv:2502.00674`)**: Sampling diverse perspectives from a single strong/fast model outperforms mixing heterogeneous weaker models (`+6.6%` AlpacaEval 2.0, `+3.8%` MMLU/CRUX/MATH). Diversity comes from the **3,456-Lens Co-Prime Matrix** (`24 Archetypes × 18 Domains × 8 Stances`), walked with a stride co-prime to $3456 = 2^7 \cdot 3^3$ so even the first 8 minds span all three axes.
2. **Adaptive-Consistency (`arXiv:2305.11860`) & ESC (`arXiv:2401.10480`)**: Models the leading cluster's vote share via a $\text{Beta}(V_1+1, V_2+1)$ posterior using Lentz continued fractions (`betai`), cutting sample spend by up to `7.9×` with `<0.1%` accuracy delta.
3. **Free-MAD (`arXiv:2509.11035`)**: Single-round structured trajectory scoring + cluster-medoid synthesis avoids multi-round sycophantic lock-in.
4. **Header-Driven `AdaptiveRateLimiter` & Pre-Flight `BudgetGuard`**: Reads `x-ratelimit-remaining-requests`, `x-ratelimit-reset-requests`, and `retry-after` live from wire headers (calibrated to Nous Portal's `400 RPM / 4M TPM`), enforces per-request and rolling daily USD caps *before* wave dispatch, and deduplicates concurrent identical calls via single-flight + SQLite content-addressed caching.

---

## Quickstart & ZothOS CLI Commands

```bash
# Offline benchmark (agreeing vs disagreeing swarm escalation)
zoth-egregore bench

# Inspect co-prime Pantheon × Domain × Stance lenses
zoth-egregore lenses -n 12

# Run one deliberation from the terminal
zoth-egregore run "What breaks first in distributed consensus under asymmetric packet loss?" --mock --json

# Launch the OpenAI-compatible server + interactive dashboard on http://127.0.0.1:8147
zoth-egregore serve --port 8147

# Run full pytest suite (54 tests)
pytest -q
```

---

## Support Open-Access Engineering

100% free and open-access. Optional support:
- ☕ **Buy Us a Coffee**: https://buy.stripe.com/3cIfZg27PdKo2D64Ocfw40X
- **Solana Tip**: `GG2eQbVh8ut1BK6j1A2tz7pSySdLpD38BgyEhGcxdXoK`

Engineered by **1nc0gn30** (`@1nc0gn30`) • [1nc0gn30.si](https://1nc0gn30.si) • [nullai.tech](https://nullai.tech)
