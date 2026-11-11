# EGREGORE (`zoth-egregore` · `:8147`) ![Status: Beta](https://img.shields.io/badge/status-experimental%20beta-ffb454?style=flat-square) ![Version: 0.1.0-beta](https://img.shields.io/badge/version-0.1.0--beta-4be3c1?style=flat-square)

`zoth-egregore` is a zero-dependency Python 3.10+ collective-intelligence inference proxy that exposes a single OpenAI-compatible model endpoint (`POST /v1/chat/completions` on `http://127.0.0.1:8147/v1`) backed by parallel DeepSeek-Flash scout calls (`deepseek/deepseek-v4.1-flash`) routed through Nous Research Hermes Agent (`~/.hermes/auth.json` / `NOUS_API_KEY` / `DEEPSEEK_API_KEY`), Beta-posterior Adaptive-Consistency stopping, and cluster-medoid synthesis collapse.

- **Web Workbench**: [https://zoth-egregore.netlify.app](https://zoth-egregore.netlify.app)
- **Zoth Studio Ecosystem**: [https://zoth.nullai.tech](https://zoth.nullai.tech)
- **Standalone Loopback Endpoint**: `http://127.0.0.1:8147/v1`
- **Support Development**: [https://buy.stripe.com/3cIfZg27PdKo2D64Ocfw40X](https://buy.stripe.com/3cIfZg27PdKo2D64Ocfw40X)

> [!NOTE]
> **Experimental Beta (`0.1.0b1`)** — Companion deliberative inference engine for DeepSeek-Flash + Nous Research Hermes Agent, verified locally under `61/61` deterministic unit and HTTP integration tests.
> - **Tests coming soon** — Expanded live-wire adversarial, red-team, and multi-turn stress test suites (61 offline orchestrator assertions active in `tests/` today).
> - **Benchmarks coming soon** — Reproducible public evaluations across GPQA-Diamond, LiveCodeBench, SWE-bench Verified, AlpacaEval 2.0, and blind UI/UX design rubrics.
> - **HuggingFace coming soon** — Open deliberation consensus traces, Design+Logic preference datasets, and distilled adapters on HuggingFace Hub.

---

## Overview

Any OpenAI-compatible client (Nous Research Hermes Agent, Python `openai` SDK, Cursor, Cline, OpenCode, `curl`, or Zoth Studio) selects deliberation depth directly via the `model` identifier with zero custom SDK extensions:

| Model String | Deliberation Mode | Behavior |
| :--- | :--- | :--- |
| `zoth-egregore` | `auto` (Adaptive) | Dispatches an 8-mind co-prime seed probe; escalates in waves (`x3.0`) only while disagreement persists; halts immediately when Beta posterior $P(\text{leader}) \ge 0.95$. |
| `zoth-egregore:probe` | `probe` (Fast Seed) | Executes one 8-mind co-prime seed wave plus synthesis collapse. |
| `zoth-egregore:50` | `fixed` (50 Minds) | Convenes 50 distinct orthogonal lenses. |
| `zoth-egregore:256` | `fixed` (256 Minds) | Convenes 256 distinct orthogonal lenses. |
| `zoth-egregore:1000` | `fixed` (Full Congress) | Convenes 1,000 distinct orthogonal lenses under adaptive RPM/TPM pacing. |
| `zoth-egregore:max` | `max` (Ceiling) | Escalates up to `max_agents` while disagreement persists. |

---

## Architecture

1. **Co-Prime 3,456-Lens Pantheon (`egregore/lenses.py`, Self-MoA `arXiv:2502.00674`)**: Combines `24 Archetypes x 18 Domains x 8 Stances = 3,456` cognitive lenses traversed via a SHA-256 stride coprime to $3456 = 2^7 \cdot 3^3$ ($\gcd(\text{stride}, 3456) = 1$), guaranteeing collision-free diversity across up to 3,456 concurrent scout prompts over `deepseek/deepseek-v4.1-flash`.
2. **Beta-Posterior Adaptive-Consistency Stopping (`egregore/consensus.py`, `arXiv:2305.11860`, `arXiv:2401.10480`)**: Computes $P(p_1 > p_2 \mid V_1, V_2) = 1 - I_{0.5}(V_1+1, V_2+1)$ via Lentz continued fractions (`betai`) with zero judge LLM calls.
3. **Free-MAD Cluster Medoid Fallback (`egregore/engine.py`, `arXiv:2509.11035`)**: Single-round independent scout exploration followed by synthesis collapse (`deepseek/deepseek-v4-pro`) and deterministic cluster-medoid fallback if synthesis errors.
4. **Formal-Logic & Design-Director Codex (`egregore/codex.py`)**: Injects domain-matched deductive reasoning invariants, 8pt/APCA UI constraints, 60fps compositor rules, and Ring-3 security checks.
5. **Zoth 77-Tool & Loopback Daemon Router (`egregore/zoth_tools.py`)**: Detects local ZothOS v3.4.0 CLI binaries and loopback daemons (`Neuro-Memory :8094`, `Adytum :8135`, `HexStrike :8138`, `Swarm Multiplexer :8141`, `WCAG Contrast Guard :8150`).
6. **Wire-Header Rate Pacing, Budget Guard & SQLite Cache (`egregore/ratelimit.py`, `budget.py`, `cache.py`)**: Tracks `x-ratelimit-remaining-*` headers, enforces per-request and rolling daily USD caps before wave dispatch, and deduplicates identical concurrent requests via single-flight + SQLite WAL caching.

---

## Quickstart

Clone the repository and install in editable mode (zero third-party runtime dependencies):

```bash
git clone https://github.com/1nc0gn30/zoth-egregore.git
cd zoth-egregore
pip install -e .

# Run offline consensus policy benchmark (agreeing vs disagreeing swarm)
zoth-egregore bench

# Run a deterministic offline deliberation with JSON output
zoth-egregore run "What breaks first in distributed consensus under asymmetric packet loss?" --mock --json
```

Configure upstream credentials via Nous Research Hermes Agent (`~/.hermes/auth.json`) or environment variables (`NOUS_API_KEY`, `DEEPSEEK_API_KEY`, or `OPENAI_API_KEY` + `EGREGORE_BASE_URL`), verify connectivity, and start the loopback server on `127.0.0.1:8147`:

```bash
zoth-egregore selftest
zoth-egregore serve --host 127.0.0.1 --port 8147
```

---

## CLI & REST API Usage

### CLI Subcommands (`zoth-egregore` / `python3 -m egregore`)

```bash
# Start the OpenAI-compatible HTTP server & dashboard on 127.0.0.1:8147
zoth-egregore serve --host 127.0.0.1 --port 8147 --max-agents 1000

# Execute a single deliberation (--mock runs offline without network calls)
zoth-egregore run "Prove or refute monotonicity here" -n 64 --mode fixed --json

# Run offline swarm escalation benchmark
zoth-egregore bench --seed 8 --min-agents 50 --max-agents 400

# Inspect generated co-prime Pantheon x Domain x Stance lenses
zoth-egregore lenses -n 12 --seed egregore

# Inspect rate-limiter, daily USD budget ledger, and SQLite cache statistics
zoth-egregore stats

# Match ZothOS v3.4.0 / Zoth Studio tools and codex domains for a prompt
zoth-egregore tools "Audit JWT claims and contrast ratios" --probe --json
```

### HTTP & OpenAI-Compatible Endpoints (`127.0.0.1:8147`)

| Method | Path | Description |
| :--- | :--- | :--- |
| `GET` | `/`, `/dashboard` | Interactive deliberation console and wave inspector |
| `GET` | `/health`, `/healthz` | Service health, active model ID, uptime, and provider key presence |
| `GET` | `/v1/models` | OpenAI model list (`zoth-egregore`, `:probe`, `:64`, `:256`, `:1000`, `:max`) |
| `POST` | `/v1/chat/completions` | OpenAI-compatible chat completions (standard JSON or `stream: true` SSE) |
| `GET` | `/v1/egregore/lenses` | Expand `n` co-prime lenses (`?n=12&seed=egregore`) |
| `GET` | `/v1/egregore/tools` | Detect ZothOS/Studio environment and match tools (`?q=<prompt>&probe=1`) |
| `GET` | `/v1/egregore/codex` | Inspect domain canons matched to `?q=<prompt>` |
| `GET` | `/v1/egregore/stats` | Rate limiter, daily spend ledger, cache stats, and recent run telemetry |

---

## Validation Roadmap

- **Tests coming soon**: Live-wire adversarial, red-team, and multi-turn stress suites augmenting the 61 deterministic offline assertions in `tests/`.
- **Benchmarks coming soon**: Reproducible benchmark harnesses for GPQA-Diamond, LiveCodeBench, SWE-bench Verified, and AlpacaEval 2.0.
- **HuggingFace coming soon**: Open deliberation consensus traces and distilled adapter weights on HuggingFace Hub.

---

## Testing & Verification

Run the 61-test `pytest` suite and offline verification commands:

```bash
python3 -m pytest -q
python3 -m egregore bench
python3 -m egregore lenses -n 8
gitleaks detect --source . --no-banner --redact
```

---

## License

MIT License. Copyright (c) 2026 1nc0gn30 (`@1nc0gn30`, [https://1nc0gn30.si](https://1nc0gn30.si)) & NullAI ([https://nullai.tech](https://nullai.tech)). See [LICENSE](LICENSE).
