"""Consensus: when has the swarm heard enough, and what is it saying?

All the text math lives here -- tokenising, similarity, clustering, voting --
plus the *stopping rule* that decides when more minds stop buying anything.
The engine supplies answers; this module supplies judgement.

The stopping rule is not invented here. It follows Adaptive-Consistency
(Aggarwal et al., EMNLP 2023, arXiv:2305.11860): sample adaptively and stop as
soon as a confident majority exists, instead of always paying for a fixed N.
Their measured result is the reason this module exists -- sample budget cut by
up to 7.9x with an average accuracy drop under 0.1%.

Specifically, the leader's share is modelled as a Beta(V1+1, V2+1) posterior
over the top two answer groups, and sampling stops once P(leader stays the
majority) >= tau (default 0.95, their C_thresh). A second, hyperparameter-free
rule from Early-Stopping Self-Consistency (arXiv:2401.10480) backs it up: if
every answer in the last `window` samples is identical, further sampling is
wasted.

Two other papers shaped what this module deliberately does NOT do:

  * Free-MAD (arXiv:2509.11035) shows single-round deliberation plus scoring
    the whole trajectory beats multi-round consensus debate, which can lock a
    wrong answer in and costs more tokens. So there is no debate loop here.
  * "Should we be going MAD?" (arXiv:2311.17371) found debate does not
    reliably beat plain sampling-and-voting at equal budget. So EGREGORE is
    honest about being self-consistency-style ensembling with an adaptive
    budget, not a debating society.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

__all__ = [
    "agreement_of",
    "beta_sf_half",
    "betai",
    "cluster_answers",
    "esc_ready",
    "medoid",
    "mean_pairwise_similarity",
    "normalize_answer",
    "stop_verdict",
    "tokens",
    "vote_counts",
    "vote_groups",
]

_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "if", "then", "than", "of", "to", "in", "on", "for",
    "with", "at", "by", "from", "as", "is", "are", "was", "were", "be", "been", "being", "it",
    "its", "this", "that", "these", "those", "you", "your", "i", "we", "they", "he", "she",
    "not", "no", "do", "does", "did", "can", "could", "should", "would", "will", "may", "might",
    "there", "here", "about", "into", "over", "after", "before", "so", "such", "very", "more",
    "most", "other", "some", "any", "all", "both", "each", "which", "who", "what", "when",
}
_WORD = re.compile(r"[a-z0-9']+")
_ANSWER_PREFIX = re.compile(r"^\s*(?:the\s+)?(?:final\s+|correct\s+)?answer\s*(?:is|:)\s*", re.I)
_CODE_FENCE = re.compile(r"^\s*```[a-zA-Z0-9+_-]*\s*|\s*```\s*$")

MAX_SIMILARITY_SAMPLE = 120  # keep agreement scoring O(sample^2), never O(1000^2)
MAX_VOTE_GROUPS = 256        # bound the vote pass; past this, exact keys only


# ---------------------------------------------------------------------------
# Text math
# ---------------------------------------------------------------------------


def tokens(text: str) -> set[str]:
    """Content words only: lowercased, stopworded, length > 2."""
    return {w for w in _WORD.findall((text or "").lower()) if w not in _STOPWORDS and len(w) > 2}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    union = len(a | b)
    return (len(a & b) / union) if union else 0.0


def mean_pairwise_similarity(texts: list[str]) -> float:
    """Mean Jaccard similarity over all pairs, sampled to stay affordable."""
    docs = [t for t in texts if t and t.strip()]
    if len(docs) < 2:
        return 1.0
    if len(docs) > MAX_SIMILARITY_SAMPLE:
        stride = len(docs) / MAX_SIMILARITY_SAMPLE
        docs = [docs[int(i * stride)] for i in range(MAX_SIMILARITY_SAMPLE)]
    toks = [tokens(d) for d in docs]
    total, n = 0.0, 0
    for i in range(len(toks)):
        for j in range(i + 1, len(toks)):
            total += jaccard(toks[i], toks[j])
            n += 1
    return total / n if n else 1.0


def agreement_of(texts: list[str]) -> tuple[float, float]:
    """(mean pairwise similarity, diversity = 1 - similarity)."""
    sim = mean_pairwise_similarity(texts)
    return sim, max(0.0, 1.0 - sim)


def cluster_answers(texts: list[str], threshold: float = 0.55) -> list[list[int]]:
    """Greedy leader clustering by similarity. Index groups, largest first."""
    toks = [tokens(t) for t in texts]
    clusters: list[list[int]] = []
    reps: list[set[str]] = []
    for i, tk in enumerate(toks):
        best, best_sim = -1, 0.0
        for ci, rep in enumerate(reps):
            sim = jaccard(tk, rep)
            if sim > best_sim:
                best, best_sim = ci, sim
        if best >= 0 and best_sim >= threshold:
            clusters[best].append(i)
        else:
            clusters.append([i])
            reps.append(tk)
    clusters.sort(key=len, reverse=True)
    return clusters


def medoid(texts: list[str], members: list[int]) -> int:
    """The member closest to all the others -- the most representative voice."""
    if len(members) == 1:
        return members[0]
    toks = {i: tokens(texts[i]) for i in members}
    best_i, best_score = members[0], -1.0
    for i in members:
        score = sum(jaccard(toks[i], toks[j]) for j in members if j != i)
        if score > best_score:
            best_i, best_score = i, score
    return best_i


# ---------------------------------------------------------------------------
# Voting
# ---------------------------------------------------------------------------


def normalize_answer(text: str) -> str:
    """A vote key: what this answer says, with the packaging removed.

    Two answers that differ only in casing, whitespace, a trailing full stop,
    a code fence, or an "The answer is" preamble must not split the vote.
    """
    t = _CODE_FENCE.sub("", (text or "").strip())
    t = re.sub(r"\s+", " ", t).strip()
    t = _ANSWER_PREFIX.sub("", t)
    t = t.strip().strip("\"'`*_# ").strip()
    t = t.rstrip(".!;:,").strip()
    return t.lower()


def vote_groups(texts: list[str], threshold: float = 0.55) -> list[list[int]]:
    """Group answers that are *saying the same thing*.

    Exact normalized keys group first (short answers: numbers, names, code);
    similar long answers group by similarity (prose). Groups come back largest
    first, which makes the count of the leader the vote share.
    """
    keys = [normalize_answer(t) for t in texts]
    by_key: dict[str, list[int]] = {}
    for i, k in enumerate(keys):
        by_key.setdefault(k, []).append(i)
    if len(by_key) <= 1:
        return [list(g) for g in by_key.values()]

    toks = [tokens(t) for t in texts]
    reps: list[set[str]] = []
    groups: list[list[int]] = []
    anchors: list[str] = []
    for key, members in by_key.items():
        tk: set[str] = set()
        for i in members:
            tk |= toks[i]
        best, best_sim = -1, 0.0
        if len(groups) < MAX_VOTE_GROUPS:
            for gi, rep in enumerate(reps):
                sim = jaccard(tk, rep)
                if sim > best_sim:
                    best, best_sim = gi, sim
        if best >= 0 and best_sim >= threshold:
            groups[best].extend(members)
        else:
            groups.append(list(members))
            reps.append(tk)
            anchors.append(key)
    groups.sort(key=len, reverse=True)
    return groups


def vote_counts(texts: list[str], threshold: float = 0.55) -> list[int]:
    """Sorted group sizes, largest first. The leader is counts[0]."""
    return [len(g) for g in vote_groups(texts, threshold)]


# ---------------------------------------------------------------------------
# Beta posterior: P(the leader stays the leader)
# ---------------------------------------------------------------------------


def _betacf(a: float, b: float, x: float, itmax: int = 300, eps: float = 3e-12) -> float:
    """Continued fraction for the incomplete beta (Numerical Recipes)."""
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < 3e-300:
        d = 3e-300
    d = 1.0 / d
    h = d
    for m in range(1, itmax + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < 3e-300:
            d = 3e-300
        c = 1.0 + aa / c
        if abs(c) < 3e-300:
            c = 3e-300
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < 3e-300:
            d = 3e-300
        c = 1.0 + aa / c
        if abs(c) < 3e-300:
            c = 3e-300
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            break
    return h


def betai(a: float, b: float, x: float) -> float:
    """Regularised incomplete beta I_x(a, b). Stdlib only, no scipy."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lbt = (math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
           + a * math.log(x) + b * math.log1p(-x))
    bt = math.exp(lbt)
    if x < (a + 1.0) / (a + b + 2.0):
        return bt * _betacf(a, b, x) / a
    return 1.0 - bt * _betacf(b, a, 1.0 - x) / b


def beta_sf_half(a: float, b: float) -> float:
    """P(X > 1/2) for X ~ Beta(a, b).

    With a = leader votes + 1 and b = runner-up votes + 1, this is the
    probability that the current leader would still be the majority if more
    answers kept arriving -- the ASC stopping quantity.
    """
    return 1.0 - betai(a, b, 0.5)


# ---------------------------------------------------------------------------
# Stopping
# ---------------------------------------------------------------------------


def esc_ready(texts: list[str], window: int = 4) -> bool:
    """ESC: the last `window` answers are identical, so sampling is wasted."""
    if window < 2 or len(texts) < window:
        return False
    keys = [normalize_answer(t) for t in texts[-window:]]
    return len(set(keys)) == 1 and bool(keys[0])


@dataclass
class StopVerdict:
    stop: bool
    confidence: float          # P(leader stays majority)
    share: float               # leader's share of the vote
    leader_votes: int
    runner_up_votes: int
    samples: int
    rule: str                  # 'asc' | 'esc' | 'short' | ''
    groups: int = 0

    def to_dict(self) -> dict:
        return {
            "stop": self.stop,
            "confidence": round(self.confidence, 4),
            "share": round(self.share, 4),
            "leader_votes": self.leader_votes,
            "runner_up_votes": self.runner_up_votes,
            "samples": self.samples,
            "rule": self.rule,
            "groups": self.groups,
        }


def stop_verdict(
    texts: list[str],
    *,
    tau: float = 0.95,
    window: int = 4,
    min_samples: int = 6,
    threshold: float = 0.55,
) -> StopVerdict:
    """Should the swarm stop collecting minds?

    Fires only on evidence: either the Beta posterior says the leader is safe
    at confidence `tau`, or the last `window` answers are identical. Until
    `min_samples` answers are in, a confident posterior is not yet trustworthy
    (with two answers both rules are trivially satisfied), so nothing stops.
    """
    docs = [t for t in texts if t and t.strip()]
    n = len(docs)
    counts = vote_counts(docs, threshold) if docs else []
    v1 = counts[0] if counts else 0
    v2 = counts[1] if len(counts) > 1 else 0
    conf = beta_sf_half(v1 + 1, v2 + 1) if n else 0.0
    share = (v1 / n) if n else 0.0

    if n < max(1, min_samples):
        return StopVerdict(False, conf, share, v1, v2, n, "", len(counts))
    if conf >= tau:
        return StopVerdict(True, conf, share, v1, v2, n, "asc", len(counts))
    if esc_ready(docs, window):
        return StopVerdict(True, conf, share, v1, v2, n, "esc", len(counts))
    return StopVerdict(False, conf, share, v1, v2, n, "", len(counts))
