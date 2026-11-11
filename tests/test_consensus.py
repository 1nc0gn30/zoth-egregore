"""Consensus math: the Beta posterior, voting, and the Adaptive-Consistency stop.

Every expected number below is hand-derivable, so these tests check the maths
rather than snapshotting whatever the code happens to do:

    P(Beta(a, b) > 1/2) for integer a, b
      = 1 - sum_{j=a}^{a+b-1} C(a+b-1, j) 0.5^(a+b-1)   (regularised incomplete beta)

    Beta(6, 2): 1 - (C(7,6)+C(7,7)) / 2^7  = 1 - 8/128  = 0.9375
    Beta(7, 2): 1 - (C(8,7)+C(8,8)) / 2^8  = 1 - 9/256  = 0.96484375
    Beta(9, 1): 1 - 0.5^9                  = 0.998046875
"""

from __future__ import annotations

import pytest

from egregore.consensus import (
    agreement_of,
    beta_sf_half,
    betai,
    cluster_answers,
    esc_ready,
    medoid,
    normalize_answer,
    stop_verdict,
    vote_counts,
    vote_groups,
)

A = "The deploy fails because the socket is never closed before the retry loop starts."
B = "Kubernetes ingress annotations must be set for the TLS certificate to resolve."
C = "Check the disk quota on the volume before blaming the application layer."
D = "The scheduler evicted the pod because of memory pressure on the node."


# ---------------------------------------------------------------------------
# Beta posterior
# ---------------------------------------------------------------------------


def test_uniform_beta_is_half():
    assert betai(1.0, 1.0, 0.5) == pytest.approx(0.5, abs=1e-12)
    assert beta_sf_half(1.0, 1.0) == pytest.approx(0.5, abs=1e-12)


def test_beta_edges():
    assert betai(3.0, 2.0, 0.0) == 0.0
    assert betai(3.0, 2.0, 1.0) == 1.0


def test_beta_sf_known_values():
    # Beta(2,1) == CDF x^2, so P(>0.5) = 1 - 0.25
    assert beta_sf_half(2.0, 1.0) == pytest.approx(0.75, abs=1e-12)
    assert beta_sf_half(9.0, 1.0) == pytest.approx(0.998046875, abs=1e-12)


def test_beta_sf_symmetric_is_half():
    assert beta_sf_half(5.0, 5.0) == pytest.approx(0.5, abs=1e-12)
    assert beta_sf_half(12.0, 12.0) == pytest.approx(0.5, abs=1e-12)


def test_beta_sf_more_leader_votes_is_more_confident():
    confs = [beta_sf_half(v + 1, 2.0) for v in range(2, 12)]
    assert confs == sorted(confs)
    assert confs[-1] > 0.99


def test_beta_sf_matches_hand_derived_posteriors():
    # A = leader votes + 1, B = runner-up votes + 1
    assert beta_sf_half(6.0, 2.0) == pytest.approx(0.9375, abs=1e-10)      # 5 vs 1
    assert beta_sf_half(7.0, 2.0) == pytest.approx(0.96484375, abs=1e-10)  # 6 vs 1


# ---------------------------------------------------------------------------
# Voting
# ---------------------------------------------------------------------------


def test_normalize_answer_strips_packaging():
    base = normalize_answer("42")
    for variant in ["42", " 42 ", "42.", "The answer is 42", "the answer is 42.",
                    "Answer: 42", "```\n42\n```", '"42"', "FINAL ANSWER: 42"]:
        assert normalize_answer(variant) == base, variant


def test_normalize_answer_keeps_meaning():
    assert normalize_answer("Cat") != normalize_answer("Dog")
    assert normalize_answer("") == ""


def test_vote_groups_merge_equivalent_answers():
    texts = ["42", "42.", "The answer is 42", D, C]
    groups = vote_groups(texts)
    assert len(groups[0]) == 3
    assert set(groups[0]) == {0, 1, 2}


def test_vote_counts_is_sorted_descending():
    texts = [A, A, A, B, C, D]
    counts = vote_counts(texts)
    assert counts[0] == 3
    assert counts == sorted(counts, reverse=True)
    assert sum(counts) == len(texts)


def test_vote_groups_do_not_merge_unrelated_prose():
    groups = vote_groups([A, B, C, D])
    assert len(groups) == 4


def test_agreement_of_extremes():
    same = [A] * 5
    assert agreement_of(same)[0] == pytest.approx(1.0)
    assert agreement_of(same)[1] == pytest.approx(0.0)
    assert agreement_of([A, B])[0] < 0.2
    assert agreement_of([A]) == (1.0, 0.0)


def test_clustering_and_medoid_agree_with_majority():
    texts = [A, A, A, B, C]
    clusters = cluster_answers(texts)
    assert len(clusters[0]) == 3
    rep = medoid(texts, clusters[0])
    assert texts[rep] == A


# ---------------------------------------------------------------------------
# Stopping
# ---------------------------------------------------------------------------


def test_esc_needs_a_full_identical_window():
    assert esc_ready([A] * 4, window=4) is True
    assert esc_ready([A] * 3, window=4) is False
    assert esc_ready([A, A, A, B], window=4) is False
    assert esc_ready(["", "", "", ""], window=4) is False


def test_stop_verdict_refuses_to_stop_too_early():
    # Two identical answers would satisfy any confidence test; min_samples
    # exists so the swarm cannot stop on a sample that small.
    v = stop_verdict([A, A], min_samples=6)
    assert v.stop is False
    assert v.rule == ""


def test_stop_verdict_stops_on_confident_leader():
    v = stop_verdict([A] * 6, tau=0.95, min_samples=6)
    assert v.stop is True
    assert v.rule == "asc"
    assert v.share == pytest.approx(1.0)
    # 6 votes and no runner-up -> Beta(7, 1): P(>1/2) = 1 - 0.5^7
    assert v.confidence == pytest.approx(0.9921875, abs=1e-10)


def test_stop_verdict_holds_when_the_vote_is_split():
    # 5 agree, 3 disagree in three separate groups -> Beta(6,2) = 0.9375 < 0.95
    v = stop_verdict([A] * 5 + [B, C, D], tau=0.95, min_samples=6)
    assert v.stop is False
    assert v.confidence == pytest.approx(0.9375, abs=1e-10)
    assert v.leader_votes == 5
    assert v.runner_up_votes == 1


def test_stop_verdict_stops_once_leader_clears_the_bar():
    # 6 vs 1 -> Beta(7,2) = 0.96484375 >= 0.95
    v = stop_verdict([A] * 6 + [B], tau=0.95, min_samples=6)
    assert v.stop is True
    assert v.confidence == pytest.approx(0.96484375, abs=1e-10)


def test_adaptive_stopping_saves_samples():
    """The point of Adaptive-Consistency: stop at 6, not at a fixed 40."""

    arriving: list[str] = []
    samples_used = 0
    for _ in range(40):
        arriving.append(A)
        samples_used += 1
        if stop_verdict(arriving, tau=0.95, min_samples=6).stop:
            break
    assert samples_used == 6
    assert samples_used < 40


def test_threshold_is_honoured():
    texts = [A] * 5 + [B, C, D]      # confidence 0.9375
    assert stop_verdict(texts, tau=0.95).stop is False
    assert stop_verdict(texts, tau=0.93).stop is True


def test_stop_verdict_on_no_answers():
    v = stop_verdict([])
    assert v.stop is False
    assert v.samples == 0
    assert v.confidence == 0.0
