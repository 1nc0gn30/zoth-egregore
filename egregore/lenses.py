"""The minds.

An egregore's power is not that it has many copies of one reasoner -- it is
that the copies *disagree in structured ways* and the disagreement is what gets
resolved. So lenses are not "agent 1..1000"; each is a named perspective built
from three axes:

    ARCHETYPE  x  DOMAIN  x  STANCE

which yields 24 x 18 x 8 = 3456 distinct lenses -- comfortably more than the
1000-agent ceiling, so no two agents in a run ever share a perspective.

Selection is deterministic given (n, seed): lenses are walked with a stride
co-prime to the product, so any prefix {lens_0..lens_n} is maximally spread
across the three axes instead of marching through archetypes one at a time.
The first eight lenses therefore already span all three axes -- which is what
makes the 8-agent seed wave a usable probe of task disagreement.

Archetypes are drawn from the Pantheon naming the ZothOS catalogue already
uses (NEXUS, DRACO, AETHER, AZOTH...), so the swarm's internal voices read as
part of the same family.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from itertools import product

# ---------------------------------------------------------------------------
# Axes
# ---------------------------------------------------------------------------

ARCHETYPES: dict[str, str] = {
    "ORACLE":     "You anticipate. Say what is about to happen and why, before the evidence is complete.",
    "SENTINEL":   "You watch for failure. Name the exact thing that breaks first, and the trigger.",
    "ARCHITECT":  "You design structure. Decompose into parts with explicit interfaces and invariants.",
    "AZOTH":      "You dissolve the problem to first principles, then rebuild only from what survives.",
    "NEXUS":      "You connect across domains. Find the non-obvious analogy that transfers.",
    "DRACO":      "You are adversarial. Attack the premise itself, not just the reasoning.",
    "AETHER":     "You seek the abstraction underneath. What is the general law here?",
    "MIMIR":      "You are the memory. What does prior art, history, or precedent already answer?",
    "JANUS":      "You hold two opposing views at once and report where they actually conflict.",
    "FULCRUM":    "You find the single leverage point where the least effort moves the most.",
    "SCRIBE":     "You compress. State the answer in the fewest correct words possible.",
    "ARTIFICER":  "You build. Give a concrete, executable, step-by-step construction.",
    "WARDEN":     "You audit constraints. What rules, limits, or compliance boundaries bind this?",
    "ANVIL":      "You stress-test. What is the worst input, and does the answer survive it?",
    "CANOPY":     "You consider second-order effects and the wider system the answer lives inside.",
    "PYTHIA":     "You reason from ambiguous or partial signals; state your confidence explicitly.",
    "HELIOS":     "You illuminate the obvious-but-unstated assumption everyone else skipped.",
    "LETHE":      "You find what is irrelevant and can be safely discarded.",
    "PROTEUS":    "You adapt the framing. Restate the question in a form that is easier to answer.",
    "TELOS":      "You ask what the answer is ultimately FOR, and optimise toward the purpose.",
    "CHORUS":     "You synthesise the middle position that most reasonable observers would accept.",
    "DAEDALUS":   "You find the path through obstacles rather than removing them.",
    "ABYSS":      "You take the idea to its extreme conclusion and report what you find there.",
    "PANTHEON":   "You enumerate the distinct viable options; do not pick, catalogue.",
}

DOMAINS: list[str] = [
    "correctness and logic",
    "performance and latency",
    "cost and resource efficiency",
    "security and abuse resistance",
    "reliability and failure modes",
    "scalability and load behaviour",
    "data integrity and consistency",
    "user experience and clarity",
    "maintainability and simplicity",
    "observability and debuggability",
    "concurrency and race conditions",
    "interoperability and standards",
    "edge cases and boundary conditions",
    "ethics and unintended harm",
    "operational deployment and rollback",
    "the human and social dimension",
    "the economics and incentives involved",
    "the long-term and second-order effects",
]

STANCES: dict[str, str] = {
    "advocate":  "Argue the strongest case FOR the leading answer.",
    "skeptic":   "Demand evidence. Mark every unsupported claim and withhold judgement.",
    "refuter":   "Actively attempt to falsify the leading answer; report only surviving objections.",
    "quant":     "Attach concrete numbers, magnitudes, or bounds wherever possible.",
    "reductive": "Reduce to the smallest sufficient explanation; cut everything else.",
    "empirical": "Reason from what has actually been observed or measured, not from theory.",
    "decisive":  "Commit to one answer and state the single most important reason for it.",
    "recursive": "Answer, then critique your own answer, then answer again after the critique.",
}

AXES = (list(ARCHETYPES), DOMAINS, list(STANCES))
PRODUCT_SIZE = len(ARCHETYPES) * len(DOMAINS) * len(STANCES)  # 3456


@dataclass(frozen=True)
class Lens:
    """One named perspective. `signature` is the human-readable identity."""

    index: int
    archetype: str
    domain: str
    stance: str

    @property
    def signature(self) -> str:
        dom = next((w for w in self.domain.split() if w.lower() != "the"), self.domain).upper()
        return f"{self.archetype}·{dom}·{self.stance}"

    def system_prompt(self) -> str:
        return (
            f"You are {self.archetype}, one mind within an egregore of many minds "
            f"deliberating as one intelligence.\n"
            f"Your lens: {self.signature}\n"
            f"{ARCHETYPES[self.archetype]}\n"
            f"Your focus is {self.domain}.\n"
            f"{STANCES[self.stance]}\n\n"
            "Rules: give your own substantive answer, not a meta-commentary about "
            "the question. 2-6 sentences. Do not say 'as an AI'. Do not open by "
            "restating the question. If you disagree with the obvious answer, say why."
        )


def _co_prime_stride(seed: int) -> int:
    """A stride co-prime with PRODUCT_SIZE so the walk visits every lens."""
    # 3456 = 2^7 * 3^3 ; any stride not divisible by 2 or 3 is co-prime.
    s = (seed % 3455) + 1
    while s % 2 == 0 or s % 3 == 0:
        s = (s % 3455) + 1
    return s


def lens_at(index: int) -> Lens:
    """Map a flat index onto (archetype, domain, stance) in row-major order."""
    i = index % PRODUCT_SIZE
    a = i % len(ARCHETYPES)
    d = (i // len(ARCHETYPES)) % len(DOMAINS)
    s = (i // (len(ARCHETYPES) * len(DOMAINS))) % len(STANCES)
    return Lens(index=index, archetype=AXES[0][a], domain=AXES[1][d], stance=AXES[2][s])


def expand(count: int, seed: str | int = 0, offset: int = 0) -> list[Lens]:
    """Deterministically pick `count` maximally-spread lenses.

    `offset` lets a later wave continue where the previous one stopped without
    ever re-using a perspective.
    """
    if count <= 0:
        return []
    seed_i = seed if isinstance(seed, int) else int(hashlib.sha256(str(seed).encode()).hexdigest()[:8], 16)
    stride = _co_prime_stride(seed_i + offset)
    start = seed_i % PRODUCT_SIZE
    out: list[Lens] = []
    seen: set[int] = set()
    step = 0
    while len(out) < count and step < PRODUCT_SIZE:
        idx = (start + offset + step * stride) % PRODUCT_SIZE
        if idx not in seen:
            seen.add(idx)
            out.append(lens_at(idx))
        step += 1
    return out


def coverage(lenses: list[Lens]) -> dict:
    """How well a lens set spans the three axes -- used for run diagnostics."""
    if not lenses:
        return {"archetypes": 0, "domains": 0, "stances": 0, "n": 0}
    return {
        "n": len(lenses),
        "archetypes": len({l.archetype for l in lenses}),
        "domains": len({l.domain for l in lenses}),
        "stances": len({l.stance for l in lenses}),
        "distinct_signatures": len({l.signature for l in lenses}),
    }
