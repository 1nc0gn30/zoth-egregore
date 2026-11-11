"""Master Design-Director, Motion, Systems & Formal Logic Codex for EGREGORE.

Distills high-craft interface judgment, motion choreography, formal deductive
rigor, systems architecture, and security hygiene into compact operational
axioms injected into DeepSeek Flash scout minds and the synthesis collapse pass.
"""

from __future__ import annotations

import re

CORE_LOGIC_SPINE = (
    "LOGIC & RIGOR INVARIANTS:\n"
    "- State explicit premises and governing invariants before deriving conclusions.\n"
    "- Separate necessary from sufficient conditions; test degenerate boundaries (0, 1, empty, N->inf).\n"
    "- Actively search for a minimal counterexample before asserting any universal claim.\n"
    "- Prefer concrete numbers, complexity bounds, and falsifiable mechanisms over vague prose."
)

DOMAIN_CANONS: dict[str, tuple[tuple[str, ...], str]] = {
    "design": (
        (
            "ui", "ux", "css", "html", "react", "tailwind", "mui", "layout", "design",
            "landing", "page", "website", "component", "typography", "font", "color",
            "colour", "contrast", "wcag", "apca", "button", "card", "grid", "hero",
            "responsive", "mobile", "viewport", "dark mode", "light mode", "theme",
        ),
        "DESIGN DIRECTOR CANON:\n"
        "- Commit to ONE anchor concept per surface; cut decoration that does not echo it.\n"
        "- Build hierarchy strictly in order: Space (8pt grid: 4/8/12/16/24/32/48/64/96px) -> "
        "Size (1.25-1.333 type scale, one focal lead) -> Mono uppercase eyebrows (11-12px, "
        "0.18-0.28em tracking) -> Contrast (>=4.5:1 body, APCA Lc>=75) -> Accent (<=10% of pixels).\n"
        "- Enforce 60-72ch paragraph measure, shared alignment axes, >=44px mobile touch targets, "
        "zero horizontal overflow (375/768/1440px), and true dual light/dark token parity.\n"
        "- Anti-slop: never use generic purple-blue blobs, emoji in section headers, mismatched "
        "button heights on one row, or fake placeholder copy.",
    ),
    "motion": (
        (
            "animation", "animate", "motion", "transition", "easing", "spring", "keyframe",
            "gsap", "framer", "canvas", "shader", "webgl", "intro", "choreography", "scroll",
            "hover", "60fps", "aperture",
        ),
        "MOTION CHOREOGRAPHY CANON:\n"
        "- Motion must explain cause->effect or spatial continuity; otherwise shorten or cut it.\n"
        "- Tokens: EASE_OUT_EXPO [0.16,1,0.3,1] entrances (450-600ms), EASE_IN_OUT [0.76,0,0.24,1] "
        "aperture shutters (650-950ms), micro-interactions 120-180ms, stagger 40-90ms (<=500ms cap).\n"
        "- Animate GPU-composited transform/opacity/clip-path only (12-24px travel, scale 0.988->1); "
        "clear ancestor transforms on transitionEnd so position:fixed descendants never break.\n"
        "- Honor prefers-reduced-motion and always provide an immediate skip escape hatch.",
    ),
    "systems": (
        (
            "distributed", "consensus", "raft", "paxos", "bft", "latency", "throughput",
            "queue", "backpressure", "rate limit", "cache", "database", "sql", "sqlite",
            "postgres", "proxy", "http", "sse", "stream", "concurrency", "thread", "async",
            "lock", "deadlock", "scale", "architecture", "daemon", "kernel",
        ),
        "SYSTEMS ARCHITECTURE CANON:\n"
        "- Size concurrency against real downstream admission limits (RPM/TPM/FD ceilings) before fan-out.\n"
        "- Coalesce identical in-flight work (single-flight), enforce idempotency and explicit timeouts, "
        "and bound every queue.\n"
        "- Separate p50 from p99 tail behavior under partial failure, packet loss, and retry storms; "
        "guarantee a non-crashing degraded fallback path.",
    ),
    "security": (
        (
            "security", "auth", "jwt", "oauth", "crypto", "encrypt", "aes", "ed25519",
            "secret", "vault", "xss", "csrf", "sqli", "ssrf", "rce", "sandbox", "landlock",
            "firewall", "prompt injection", "egress", "osint", "cve", "yara", "threat",
        ),
        "SOVEREIGN SECURITY CANON:\n"
        "- Enumerate trust boundaries first; treat all external inputs, model outputs, and tool args as untrusted.\n"
        "- Enforce least privilege (Ring-3 / Landlock / ephemeral ports), constant-time verification, "
        "strict origin/path canonicalization, and zero plaintext secret persistence on disk.",
    ),
    "code": (
        (
            "python", "javascript", "typescript", "rust", "go", "bash", "function", "class",
            "bug", "refactor", "test", "pytest", "vitest", "implement", "script", "cli",
            "api", "algorithm", "optimize",
        ),
        "ENGINEERING & VERIFICATION CANON:\n"
        "- Prefer small, composable, zero-bloat stdlib primitives with explicit types and invariants.\n"
        "- Never ship fake stubs or silent exception swallows; handle empty/malformed/concurrent edge cases "
        "and state how the solution is deterministically verified.",
    ),
}


def detect_domains(prompt: str, max_domains: int = 2) -> list[str]:
    """Return the top matched specialist canons for `prompt`."""
    text = (prompt or "").lower()
    if not text.strip():
        return ["code"]
    scored: list[tuple[int, str]] = []
    for name, (keywords, _canon) in DOMAIN_CANONS.items():
        hits = sum(1 for kw in keywords if re.search(r"\b" + re.escape(kw) + r"\b", text))
        if hits > 0:
            scored.append((hits, name))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [name for _, name in scored[:max_domains]] or ["code"]


def codex_for_prompt(prompt: str, *, include_domains: bool = True) -> tuple[str, list[str]]:
    """Build the compact Codex block and list of active domain tags."""
    domains = detect_domains(prompt) if include_domains else []
    blocks = [CORE_LOGIC_SPINE]
    for dom in domains:
        entry = DOMAIN_CANONS.get(dom)
        if entry:
            blocks.append(entry[1])
    return "\n\n".join(blocks), ["logic", *domains]
