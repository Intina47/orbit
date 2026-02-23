from __future__ import annotations

from orbit.eval_harness import (
    EvalQuery,
    EvalRecord,
    QueryScore,
    RankedItem,
    aggregate_query_scores,
    baseline_score,
    evaluate_ranking,
    tokenize,
)


def test_tokenize_normalizes_words() -> None:
    tokens = tokenize("Alice's Python-Loop basics, v2!")
    assert "alice" in tokens
    assert "python" in tokens
    assert "loop" in tokens
    assert "v2" in tokens


def test_baseline_score_biases_long_assistant_noise() -> None:
    query = "How should I explain python loops to alice?"
    relevant = EvalRecord(
        content="PROFILE: Alice prefers short explanations for loops.",
        event_type="preference_stated",
        entity_id="alice",
        order=1,
    )
    noisy = EvalRecord(
        content=(
            "ASSISTANT_LONG: "
            + "python loops alice explanation " * 80
        ),
        event_type="assistant_response",
        entity_id="alice",
        order=2,
    )
    assert baseline_score(query=query, record=noisy, total=10) > baseline_score(
        query=query,
        record=relevant,
        total=10,
    )


def test_evaluate_ranking_computes_query_metrics() -> None:
    query = EvalQuery(
        query_id="q1",
        query="How should I teach Alice?",
        entity_id="alice",
        relevant_contents=frozenset({"PROFILE: Alice prefers analogies."}),
        stale_contents=frozenset({"PROFILE_OLD: Alice is a beginner."}),
    )
    ranked = [
        RankedItem(
            content="PROFILE: Alice prefers analogies.",
            event_type="preference_stated",
            score=0.9,
        ),
        RankedItem(
            content="ASSISTANT_LONG: generic response",
            event_type="assistant_response",
            score=0.7,
        ),
        RankedItem(
            content="PROFILE_OLD: Alice is a beginner.",
            event_type="preference_stated",
            score=0.6,
        ),
    ]
    score = evaluate_ranking(query=query, ranked=ranked)
    assert score.precision_at_5 == 1.0 / 3.0
    assert score.top1_relevant == 1.0
    assert score.personalization_hit == 1.0
    assert score.assistant_noise_rate == 1.0 / 3.0
    assert score.stale_memory_rate == 1.0 / 3.0
    assert score.predicted_helpful == 0.0


def test_aggregate_query_scores() -> None:
    metrics = aggregate_query_scores(
        [
            QueryScore(1.0, 1.0, 1.0, 0.0, 0.0, 1.0),
            QueryScore(0.5, 0.0, 1.0, 0.2, 0.1, 0.0),
        ]
    )
    assert metrics["avg_precision_at_5"] == 0.75
    assert metrics["top1_relevant_rate"] == 0.5
    assert metrics["assistant_noise_rate"] == 0.1
    assert metrics["stale_memory_rate"] == 0.05
