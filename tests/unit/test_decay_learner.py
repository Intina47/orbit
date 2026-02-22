from __future__ import annotations

from decision_engine.decay_learner import DecayLearner


def test_decay_rate_increases_for_stale_unhelpful_memories() -> None:
    learner = DecayLearner(learning_rate=0.01, prior_decay_rate=0.01)
    semantic_key = "user-preference"

    for age in [1.0, 2.0, 3.0]:
        learner.record_outcome(
            semantic_key=semantic_key, age_days=age, was_helpful=True
        )
    for age in [20.0, 25.0, 30.0]:
        learner.record_outcome(
            semantic_key=semantic_key, age_days=age, was_helpful=False
        )

    initial_rate = learner.predict_decay_rate(semantic_key)
    learner.learn()
    updated_rate = learner.predict_decay_rate(semantic_key)

    assert updated_rate > initial_rate


def test_relevance_decays_with_age() -> None:
    learner = DecayLearner(learning_rate=0.01, prior_decay_rate=0.02)
    key = "task-log"
    now = learner.predict_relevance(key, age_days=0.0, initial_importance=1.0)
    later = learner.predict_relevance(key, age_days=30.0, initial_importance=1.0)
    assert later < now
