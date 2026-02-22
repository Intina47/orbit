from __future__ import annotations

from memory_engine.stage2_decision.scoring import bootstrap_relevance_score


def test_recency_exponential_decay() -> None:
    score_now = bootstrap_relevance_score(
        recency_days=0, frequency_count=5, entity_ref_count=10
    )
    score_7d = bootstrap_relevance_score(
        recency_days=7, frequency_count=5, entity_ref_count=10
    )
    assert score_now > score_7d


def test_frequency_saturation() -> None:
    score_1x = bootstrap_relevance_score(
        recency_days=0, frequency_count=1, entity_ref_count=10
    )
    score_20x = bootstrap_relevance_score(
        recency_days=0, frequency_count=20, entity_ref_count=10
    )
    assert score_20x < 1.0
    assert score_20x > score_1x


def test_weight_proportions_and_bounds() -> None:
    score = bootstrap_relevance_score(
        recency_days=0, frequency_count=50, entity_ref_count=50
    )
    assert 0.9 < score <= 1.0
