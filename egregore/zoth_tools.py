"""Native In-House ZothOS, Zoth Studio & Hermes-Zoth Tool Orchestrator.

Connects EGREGORE to the 77-tool Zoth Sovereign Arsenal and 23 local loopback
daemons. When EGREGORE runs on ZothOS (`https://zothos.nullai.tech`) or beside
Zoth Studio (`https://zoth.nullai.tech`), it automatically discovers installed
CLI binaries and live loopback daemons (`Neuro-Memory :8094`, `Adytum :8135`,
`HexStrike :8138`, `Swarm Multiplexer :8141`, `Zoth-Relay :8765`), enriching
deliberations with real local tool capabilities and daemon telemetry.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import socket
import urllib.request
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ZothToolSpec:
    id: str
    name: str
    cli: str
    port: int | None
    category: str
    keywords: tuple[str, ...]
    summary: str
    invoke_hint: str


# Core high-leverage Zoth tools always known to Egregore (augmented dynamically
# from Zoth Studio / hermes-zoth catalog files when installed locally).
BUILTIN_ZOTH_TOOLS: tuple[ZothToolSpec, ...] = (
    ZothToolSpec(
        id="neuro-memory-daemon",
        name="Neuro-Memory Daemon (Hebbian STDP)",
        cli="neuro-memory-daemon",
        port=8094,
        category="Memory & Knowledge",
        keywords=("memory", "recall", "context", "knowledge", "graph", "wiki", "obsidian", "stdp", "engram", "history"),
        summary="Sub-millisecond Hebbian STDP episodic memory graph & Karpathy wiki recall daemon on :8094.",
        invoke_hint="neuro-memory-daemon --status | GET http://127.0.0.1:8094/health",
    ),
    ZothToolSpec(
        id="adytum-planner",
        name="Adytum DAG & Goal Planner",
        cli="adytum",
        port=8135,
        category="Swarm & Core",
        keywords=("plan", "roadmap", "dag", "schedule", "milestone", "task", "architecture", "decompose", "strategy"),
        summary="Deterministic DAG task decomposition, critical-path scheduling, and milestone verification on :8135.",
        invoke_hint="adytum --status | GET http://127.0.0.1:8135/health",
    ),
    ZothToolSpec(
        id="zoth-swarm-multiplexer",
        name="21-Agent Swarm Multiplexer",
        cli="zoth-swarm-multiplexer",
        port=8141,
        category="Swarm & Core",
        keywords=("swarm", "multi-agent", "pty", "terminal", "multiplexer", "byzantine", "quorum", "parallel", "orchestrate"),
        summary="21-pane PTY terminal multiplexer with hot-swappable Hermes/DeepSeek harnesses and PBFT quorum telemetry on :8141.",
        invoke_hint="zoth-swarm-multiplexer --status",
    ),
    ZothToolSpec(
        id="wcag-contrast-guard",
        name="WCAG & APCA Contrast Guard",
        cli="wcag-contrast-guard",
        port=8150,
        category="Design & UI",
        keywords=("ui", "ux", "design", "color", "colour", "contrast", "wcag", "apca", "palette", "accessibility", "theme", "light mode", "dark mode"),
        summary="Audits foreground/background token pairs against WCAG 2.2 AA/AAA and APCA Lc perceptual contrast thresholds.",
        invoke_hint="wcag-contrast-guard --help",
    ),
    ZothToolSpec(
        id="reality-shader-forge",
        name="Reality Shader & Theme Forge",
        cli="reality-forge",
        port=8118,
        category="Design & UI",
        keywords=("shader", "webgl", "glsl", "canvas", "dither", "braille", "ascii", "motion", "animation", "visual", "theme"),
        summary="Procedural WebGL2 GLSL shader, Bayer dither, and dual-theme design token forge.",
        invoke_hint="reality-forge --status",
    ),
    ZothToolSpec(
        id="cwv-speed-engine",
        name="Core Web Vitals Speed Engine",
        cli="cwv-speed-engine",
        port=8128,
        category="Web & Performance",
        keywords=("performance", "lcp", "cls", "inp", "lighthouse", "bundle", "speed", "latency", "render", "web", "frontend"),
        summary="Static & runtime analyzer for LCP, INP, CLS, asset weight, and render-blocking critical paths.",
        invoke_hint="cwv-speed-engine --help",
    ),
    ZothToolSpec(
        id="aeo-graph-engine",
        name="AEO & Schema.org Graph Engine",
        cli="aeo-graph-engine",
        port=8127,
        category="SEO & AEO",
        keywords=("seo", "aeo", "schema", "json-ld", "llms.txt", "sitemap", "robots.txt", "opengraph", "search", "crawler"),
        summary="Synthesizes and validates Schema.org @graph JSON-LD, FAQPage, llms.txt, and frontier crawler directives.",
        invoke_hint="aeo-graph-engine --help",
    ),
    ZothToolSpec(
        id="zoth-webgen",
        name="Zoth WebGen Studio",
        cli="zoth-webgen",
        port=5173,
        category="Design & UI",
        keywords=("website", "landing", "webapp", "fullstack", "vite", "react", "scaffold", "deploy", "component"),
        summary="Autonomous full-stack UI & web application generator with triple-viewport guardrail verification.",
        invoke_hint="zoth-webgen --help",
    ),
    ZothToolSpec(
        id="hexstrike-security",
        name="HexStrike Security Arsenal",
        cli="hexstrike",
        port=8138,
        category="Security & Recon",
        keywords=("security", "pentest", "cve", "vuln", "exploit", "binary", "elf", "audit", "hardening", "redteam"),
        summary="Defensive binary auditing, CVE surface triage, and sandboxed security verification suite on :8138.",
        invoke_hint="hexstrike --status",
    ),
    ZothToolSpec(
        id="agent-prompt-firewall",
        name="Agent Prompt Firewall",
        cli="agent-prompt-firewall",
        port=8098,
        category="Agent Safety",
        keywords=("prompt injection", "jailbreak", "firewall", "guardrail", "untrusted", "sanitize", "policy", "llm security"),
        summary="Deterministic lexical + structural firewall against indirect prompt injection and tool-call hijacking.",
        invoke_hint="agent-prompt-firewall --help",
    ),
    ZothToolSpec(
        id="envguard-secrets-vault",
        name="EnvGuard Secrets Vault",
        cli="envguard",
        port=8088,
        category="Security & Recon",
        keywords=("secret", "env", "dotenv", "api key", "token", "leak", "gitleaks", "entropy", "vault", "credential"),
        summary="Zero-egress Shannon entropy & pattern scanner for .env files, JWTs, and repository secret hygiene.",
        invoke_hint="envguard --help",
    ),
    ZothToolSpec(
        id="zoth-osint",
        name="Zoth OSINT Workstation",
        cli="zoth-osint",
        port=8149,
        category="Security & Recon",
        keywords=("osint", "domain", "dns", "subdomain", "recon", "ct log", "breach", "mitre", "stix"),
        summary="32-tool OSINT correlation engine with k-anonymity breach checks, subdomain takeover audit, and STIX 2.1 export.",
        invoke_hint="zoth-osint --status --json",
    ),
    ZothToolSpec(
        id="zoth-relay",
        name="Zoth-Relay Landlock Bridge",
        cli="zoth-relay",
        port=8765,
        category="Swarm & Core",
        keywords=("relay", "landlock", "sandbox", "ipc", "bridge", "mcp", "isolation", "ring"),
        summary="Kernel Landlock-isolated multi-agent IPC & MCP tool relay on :8765.",
        invoke_hint="zoth-relay --help",
    ),
    ZothToolSpec(
        id="jwt-inspector-guard",
        name="JWT Inspector Guard",
        cli="jwt-inspector-guard",
        port=8124,
        category="Security & Recon",
        keywords=("jwt", "jws", "hs256", "rs256", "alg none", "bearer", "oauth", "session", "claims"),
        summary="Cryptographic JWT/JWS signature verifier and CVE-2015-9235 alg:none / weak-HMAC auditor.",
        invoke_hint="jwt-inspector-guard --help",
    ),
)


def _port_open(port: int | None, timeout: float = 0.12) -> bool:
    if not port:
        return False
    try:
        with socket.create_connection(("127.0.0.1", int(port)), timeout=timeout):
            return True
    except OSError:
        return False


def _probe_json(url: str, timeout: float = 0.25) -> dict | None:
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - loopback only
            if resp.status == 200:
                return json.loads(resp.read().decode("utf-8", "replace"))
    except Exception:
        return None
    return None


def detect_zoth_environment(probe_daemons: bool = False) -> dict:
    """Inspect local ZothOS, Zoth Studio, and Hermes-Zoth installation state."""
    home = Path(os.path.expanduser("~"))
    studio_catalog = home / "NullAITech" / "zoth-studio-v2" / "public" / "api" / "tools.json"
    hermes_catalog = home / "NullAITech" / "hermes-zoth" / "data" / "studio_tools.json"
    hermes_auth = Path(os.environ.get("HERMES_HOME", home / ".hermes")) / "auth.json"
    is_zothos = Path("/etc/zothos-release").exists() or Path("/opt/zoth-studio").exists()

    catalog_count = len(BUILTIN_ZOTH_TOOLS)
    for cand in (studio_catalog, hermes_catalog):
        if cand.is_file():
            try:
                raw = json.loads(cand.read_text(encoding="utf-8"))
                items = raw if isinstance(raw, list) else raw.get("tools", [])
                if items:
                    catalog_count = len(items)
                    break
            except Exception:
                pass

    installed_clis = sum(1 for t in BUILTIN_ZOTH_TOOLS if shutil.which(t.cli))
    live_daemons: list[str] = []
    if probe_daemons:
        for t in BUILTIN_ZOTH_TOOLS:
            if t.port and _port_open(t.port):
                live_daemons.append(f"{t.id}:{t.port}")

    tier = (
        "zothos-native"
        if is_zothos
        else ("zoth-studio" if studio_catalog.is_file() or installed_clis >= 3 else "standalone")
    )
    return {
        "tier": tier,
        "zothos_detected": is_zothos,
        "zoth_studio_detected": studio_catalog.is_file() or _port_open(3000) if probe_daemons else studio_catalog.is_file(),
        "hermes_profile_detected": hermes_auth.is_file(),
        "catalog_tools_total": catalog_count,
        "core_clis_installed": installed_clis,
        "core_clis_checked": len(BUILTIN_ZOTH_TOOLS),
        "live_daemons": live_daemons,
    }


def match_tools_for_prompt(prompt: str, limit: int = 4, probe_local: bool = False) -> list[dict]:
    """Select the most relevant in-house Zoth tools for `prompt`."""
    text = (prompt or "").lower()
    scored: list[tuple[int, ZothToolSpec]] = []
    for spec in BUILTIN_ZOTH_TOOLS:
        score = 0
        for kw in spec.keywords:
            if re.search(r"\b" + re.escape(kw) + r"\b", text):
                score += 2
            elif kw in text:
                score += 1
        if score > 0:
            scored.append((score, spec))

    if not scored:
        # Default architectural triad: Planner + Memory + Swarm
        defaults = ("adytum-planner", "neuro-memory-daemon", "zoth-swarm-multiplexer")
        scored = [(1, s) for s in BUILTIN_ZOTH_TOOLS if s.id in defaults]

    scored.sort(key=lambda item: (-item[0], item[1].id))
    out: list[dict] = []
    for score, spec in scored[:limit]:
        cli_path = shutil.which(spec.cli)
        daemon_up = _port_open(spec.port) if (probe_local and spec.port) else False
        health = _probe_json(f"http://127.0.0.1:{spec.port}/health") if daemon_up else None
        out.append({
            "id": spec.id,
            "name": spec.name,
            "cli": spec.cli,
            "port": spec.port,
            "category": spec.category,
            "relevance_score": score,
            "installed_locally": bool(cli_path),
            "daemon_online": daemon_up,
            "daemon_health": health.get("status") if isinstance(health, dict) else None,
            "summary": spec.summary,
            "invoke_hint": spec.invoke_hint,
        })
    return out


def build_tool_augmentation_block(prompt: str, *, probe_local: bool = False) -> tuple[str, list[dict]]:
    """Build a compact prompt-enrichment block describing matched in-house Zoth tools."""
    matched = match_tools_for_prompt(prompt, limit=3, probe_local=probe_local)
    if not matched:
        return "", []
    lines = [
        "IN-HOUSE ZOTH ARSENAL TOOLS AVAILABLE TO THE OPERATOR (reference or emit exact commands ONLY when genuinely helpful):"
    ]
    for m in matched:
        state = "LIVE DAEMON" if m["daemon_online"] else ("CLI INSTALLED" if m["installed_locally"] else "ZothOS/Studio Tool")
        lines.append(f"- {m['name']} [{state}] (`{m['invoke_hint']}`): {m['summary']}")
    return "\n".join(lines), matched
