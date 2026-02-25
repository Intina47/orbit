from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import tempfile
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Callable

import numpy as np
from numpy.typing import NDArray

from decision_engine.models import MemoryRecord, StorageTier
from decision_engine.retrieval_ranker import RetrievalRanker as CurrentRetrievalRanker

FloatArray = NDArray[np.float32]


@dataclass(frozen=True)
class Scenario:
    name: str
    query_embedding: FloatArray
    candidates: list[MemoryRecord]
    helpful_memory_ids: set[str]
    now: datetime


def _unit(vec: NDArray[np.float64]) -> FloatArray:
    norm = float(np.linalg.norm(vec))
    if norm == 0.0:
        return np.zeros_like(vec, dtype=np.float32)
    return np.asarray(vec / norm, dtype=np.float32)


def _rand_unit(rng: np.random.Generator, dim: int) -> FloatArray:
    return _unit(rng.normal(size=dim))


def _memory(
    *,
    memory_id: str,
    embedding: FloatArray,
    created_at: datetime,
    updated_at: datetime,
    retrieval_count: int,
    avg_outcome_signal: float,
    intent: str,
    summary: str,
    content: str,
    latest_importance: float,
) -> MemoryRecord:
    return MemoryRecord(
        memory_id=memory_id,
        event_id=f"event-{memory_id}",
        content=content,
        summary=summary,
        intent=intent,
        entities=["alice"],
        relationships=[],
        raw_embedding=embedding.tolist(),
        semantic_embedding=embedding.tolist(),
        semantic_key=f"key-{memory_id}",
        created_at=created_at,
        updated_at=updated_at,
        retrieval_count=retrieval_count,
        avg_outcome_signal=avg_outcome_signal,
        storage_tier=StorageTier.PERSISTENT,
        latest_importance=latest_importance,
    )


def _scenario_reinforcement(
    *,
    idx: int,
    rng: np.random.Generator,
    dim: int,
    now: datetime,
) -> Scenario:
    query = _rand_unit(rng, dim)
    near = _unit(
        np.asarray(query, dtype=np.float64) * 0.92
        + np.asarray(_rand_unit(rng, dim), dtype=np.float64) * 0.08
    )
    distract = _rand_unit(rng, dim)
    stale_created = now - timedelta(days=52)
    stale = _memory(
        memory_id=f"reinforce-stale-{idx}",
        embedding=near,
        created_at=stale_created,
        updated_at=stale_created,
        retrieval_count=0,
        avg_outcome_signal=0.0,
        intent="learning_progress",
        summary="Alice STAR interview prep context.",
        content="STAR interview prep context for role-specific responses.",
        latest_importance=0.81,
    )
    revived = _memory(
        memory_id=f"reinforce-revived-{idx}",
        embedding=near,
        created_at=stale_created,
        updated_at=now - timedelta(days=1),
        retrieval_count=0,
        avg_outcome_signal=0.0,
        intent="learning_progress",
        summary="Alice STAR interview prep context.",
        content="STAR interview prep context for role-specific responses.",
        latest_importance=0.81,
    )
    noise = _memory(
        memory_id=f"reinforce-noise-{idx}",
        embedding=distract,
        created_at=now - timedelta(days=3),
        updated_at=now - timedelta(days=3),
        retrieval_count=0,
        avg_outcome_signal=-0.1,
        intent="assistant_response",
        summary="Long answer blob.",
        content="assistant response " * 240,
        latest_importance=0.52,
    )
    return Scenario(
        name="reinforcement_refresh",
        query_embedding=query,
        candidates=[stale, revived, noise],
        helpful_memory_ids={revived.memory_id},
        now=now,
    )


def _scenario_constraint(
    *,
    idx: int,
    rng: np.random.Generator,
    dim: int,
    now: datetime,
) -> Scenario:
    query = _rand_unit(rng, dim)
    near = _unit(
        np.asarray(query, dtype=np.float64) * 0.88
        + np.asarray(_rand_unit(rng, dim), dtype=np.float64) * 0.12
    )
    competitor = _unit(
        np.asarray(query, dtype=np.float64) * 0.90
        + np.asarray(_rand_unit(rng, dim), dtype=np.float64) * 0.10
    )
    old_time = now - timedelta(days=95)
    constraint = _memory(
        memory_id=f"constraint-{idx}",
        embedding=near,
        created_at=old_time,
        updated_at=old_time,
        retrieval_count=0,
        avg_outcome_signal=0.0,
        intent="user_fact",
        summary="User has knee injury risk for military medical exam.",
        content="My knee injury may be an issue for the medical exam.",
        latest_importance=0.76,
    )
    ephemeral = _memory(
        memory_id=f"constraint-ephemeral-{idx}",
        embedding=competitor,
        created_at=old_time,
        updated_at=old_time,
        retrieval_count=1,
        avg_outcome_signal=0.0,
        intent="user_question",
        summary="Question about writing another CV draft.",
        content="Help me rewrite my CV opening summary.",
        latest_importance=0.88,
    )
    assistant = _memory(
        memory_id=f"constraint-assistant-{idx}",
        embedding=competitor,
        created_at=now - timedelta(days=4),
        updated_at=now - timedelta(days=4),
        retrieval_count=1,
        avg_outcome_signal=-0.1,
        intent="assistant_response",
        summary="assistant response",
        content="assistant response " * 150,
        latest_importance=0.56,
    )
    return Scenario(
        name="constraint_retention",
        query_embedding=query,
        candidates=[ephemeral, constraint, assistant],
        helpful_memory_ids={constraint.memory_id},
        now=now,
    )


def _scenario_assistant_noise(
    *,
    idx: int,
    rng: np.random.Generator,
    dim: int,
    now: datetime,
) -> Scenario:
    query = _rand_unit(rng, dim)
    profile_emb = _unit(
        np.asarray(query, dtype=np.float64) * 0.89
        + np.asarray(_rand_unit(rng, dim), dtype=np.float64) * 0.11
    )
    assistant_emb = _unit(
        np.asarray(query, dtype=np.float64) * 0.92
        + np.asarray(_rand_unit(rng, dim), dtype=np.float64) * 0.08
    )
    profile = _memory(
        memory_id=f"profile-{idx}",
        embedding=profile_emb,
        created_at=now - timedelta(days=8),
        updated_at=now - timedelta(days=8),
        retrieval_count=1,
        avg_outcome_signal=0.4,
        intent="preference_stated",
        summary="Alice prefers concise explanations with examples.",
        content="Keep explanations concise and practical for Alice.",
        latest_importance=0.90,
    )
    assistant = _memory(
        memory_id=f"assistant-{idx}",
        embedding=assistant_emb,
        created_at=now - timedelta(days=1),
        updated_at=now - timedelta(days=1),
        retrieval_count=2,
        avg_outcome_signal=-0.3,
        intent="assistant_response",
        summary="assistant response " * 130,
        content="assistant response " * 750,
        latest_importance=0.68,
    )
    distract = _memory(
        memory_id=f"profile-noise-{idx}",
        embedding=_rand_unit(rng, dim),
        created_at=now - timedelta(days=2),
        updated_at=now - timedelta(days=2),
        retrieval_count=0,
        avg_outcome_signal=0.0,
        intent="user_question",
        summary="Unrelated question.",
        content="What is a closure in JavaScript?",
        latest_importance=0.65,
    )
    return Scenario(
        name="assistant_noise_control",
        query_embedding=query,
        candidates=[assistant, profile, distract],
        helpful_memory_ids={profile.memory_id},
        now=now,
    )


def _scenario_context_shift(
    *,
    idx: int,
    rng: np.random.Generator,
    dim: int,
    now: datetime,
) -> Scenario:
    query = _rand_unit(rng, dim)
    fit = _unit(
        np.asarray(query, dtype=np.float64) * 0.91
        + np.asarray(_rand_unit(rng, dim), dtype=np.float64) * 0.09
    )
    stale_fit = _unit(
        np.asarray(query, dtype=np.float64) * 0.91
        + np.asarray(_rand_unit(rng, dim), dtype=np.float64) * 0.09
    )
    new_progress = _memory(
        memory_id=f"ctx-new-{idx}",
        embedding=fit,
        created_at=now - timedelta(days=4),
        updated_at=now - timedelta(days=2),
        retrieval_count=2,
        avg_outcome_signal=0.3,
        intent="learning_progress",
        summary="User advanced from beginner to intermediate interview prep.",
        content="I got invited for interview and now need advanced prep.",
        latest_importance=0.84,
    )
    old_progress = _memory(
        memory_id=f"ctx-old-{idx}",
        embedding=stale_fit,
        created_at=now - timedelta(days=65),
        updated_at=now - timedelta(days=65),
        retrieval_count=1,
        avg_outcome_signal=-0.1,
        intent="learning_progress",
        summary="User is a complete beginner.",
        content="I'm a total beginner and need basics only.",
        latest_importance=0.82,
    )
    distract = _memory(
        memory_id=f"ctx-noise-{idx}",
        embedding=_rand_unit(rng, dim),
        created_at=now - timedelta(days=1),
        updated_at=now - timedelta(days=1),
        retrieval_count=0,
        avg_outcome_signal=0.0,
        intent="assistant_response",
        summary="assistant response",
        content="assistant response " * 110,
        latest_importance=0.60,
    )
    return Scenario(
        name="progress_freshness",
        query_embedding=query,
        candidates=[old_progress, new_progress, distract],
        helpful_memory_ids={new_progress.memory_id},
        now=now,
    )


def _scenario_generators() -> list[Callable[..., Scenario]]:
    return [
        _scenario_reinforcement,
        _scenario_constraint,
        _scenario_assistant_noise,
        _scenario_context_shift,
    ]


def _generate_scenarios(
    *,
    per_class: int,
    seed: int,
    dim: int,
) -> list[Scenario]:
    rng = np.random.default_rng(seed)
    generators = _scenario_generators()
    all_scenarios: list[Scenario] = []
    now = datetime.now(UTC)
    for idx in range(per_class):
        for gen in generators:
            all_scenarios.append(gen(idx=idx, rng=rng, dim=dim, now=now))
    return all_scenarios


def _load_baseline_ranker_class() -> type[Any]:
    source = subprocess.check_output(
        ["git", "show", "HEAD:src/decision_engine/retrieval_ranker.py"],
        text=True,
    )
    with tempfile.TemporaryDirectory(prefix="orbit-ranker-baseline-") as tmp_dir:
        path = Path(tmp_dir) / "baseline_ranker.py"
        path.write_text(source, encoding="utf-8")
        spec = importlib.util.spec_from_file_location("baseline_ranker", path)
        if spec is None or spec.loader is None:
            msg = "failed to load baseline ranker module spec"
            raise RuntimeError(msg)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        cls = getattr(module, "RetrievalRanker", None)
        if cls is None:
            msg = "baseline RetrievalRanker class not found"
            raise RuntimeError(msg)
        return cls


def _evaluate_ranker(
    ranker_cls: type[Any],
    *,
    train_scenarios: list[Scenario],
    eval_scenarios: list[Scenario],
    min_training_samples: int,
    training_batch_size: int,
    train: bool,
) -> dict[str, Any]:
    ranker = ranker_cls(
        min_training_samples=min_training_samples,
        training_batch_size=training_batch_size,
    )
    if train:
        for scenario in train_scenarios:
            ranker.learn_from_feedback(
                query_embedding=scenario.query_embedding,
                candidates=scenario.candidates,
                helpful_memory_ids=scenario.helpful_memory_ids,
                now=scenario.now,
            )

    by_class: dict[str, dict[str, float]] = defaultdict(
        lambda: {
            "count": 0.0,
            "top1": 0.0,
            "precision_at_3": 0.0,
        }
    )
    overall_count = 0.0
    overall_top1 = 0.0
    overall_p3 = 0.0

    for scenario in eval_scenarios:
        ranked = ranker.rank(
            query_embedding=scenario.query_embedding,
            candidates=scenario.candidates,
            now=scenario.now,
        )
        top1_hit = (
            1.0
            if ranked and ranked[0].memory.memory_id in scenario.helpful_memory_ids
            else 0.0
        )
        top_k = min(3, len(ranked))
        if top_k == 0:
            p3 = 0.0
        else:
            hits = sum(
                1
                for item in ranked[:top_k]
                if item.memory.memory_id in scenario.helpful_memory_ids
            )
            p3 = hits / float(top_k)

        bucket = by_class[scenario.name]
        bucket["count"] += 1.0
        bucket["top1"] += top1_hit
        bucket["precision_at_3"] += p3

        overall_count += 1.0
        overall_top1 += top1_hit
        overall_p3 += p3

    class_metrics: dict[str, dict[str, float]] = {}
    for name, agg in by_class.items():
        count = max(agg["count"], 1.0)
        class_metrics[name] = {
            "count": agg["count"],
            "top1_relevant_rate": agg["top1"] / count,
            "precision_at_3": agg["precision_at_3"] / count,
        }
    overall_den = max(overall_count, 1.0)
    return {
        "overall": {
            "count": overall_count,
            "top1_relevant_rate": overall_top1 / overall_den,
            "precision_at_3": overall_p3 / overall_den,
            "trained": bool(getattr(ranker, "is_trained", False)),
        },
        "by_class": class_metrics,
    }


def _delta(new: dict[str, Any], base: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {
        "overall": {},
        "by_class": {},
    }
    for key in ("top1_relevant_rate", "precision_at_3"):
        out["overall"][key] = (
            float(new["overall"][key]) - float(base["overall"][key])
        )

    class_names = sorted(set(new["by_class"].keys()) | set(base["by_class"].keys()))
    for name in class_names:
        n = new["by_class"].get(name, {})
        b = base["by_class"].get(name, {})
        out["by_class"][name] = {
            "top1_relevant_rate": float(n.get("top1_relevant_rate", 0.0))
            - float(b.get("top1_relevant_rate", 0.0)),
            "precision_at_3": float(n.get("precision_at_3", 0.0))
            - float(b.get("precision_at_3", 0.0)),
        }
    return out


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Stress test current decay model vs previous HEAD ranker."
    )
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--dim", type=int, default=24)
    parser.add_argument("--train-per-class", type=int, default=80)
    parser.add_argument("--eval-per-class", type=int, default=240)
    parser.add_argument("--output", type=Path, default=Path("quality_reports/decay_ab.json"))
    args = parser.parse_args()

    baseline_cls = _load_baseline_ranker_class()
    train_scenarios = _generate_scenarios(
        per_class=args.train_per_class,
        seed=args.seed,
        dim=args.dim,
    )
    eval_scenarios = _generate_scenarios(
        per_class=args.eval_per_class,
        seed=args.seed + 1,
        dim=args.dim,
    )

    baseline_cold = _evaluate_ranker(
        baseline_cls,
        train_scenarios=train_scenarios,
        eval_scenarios=eval_scenarios,
        min_training_samples=10_000,
        training_batch_size=64,
        train=False,
    )
    current_cold = _evaluate_ranker(
        CurrentRetrievalRanker,
        train_scenarios=train_scenarios,
        eval_scenarios=eval_scenarios,
        min_training_samples=10_000,
        training_batch_size=64,
        train=False,
    )
    baseline_warm = _evaluate_ranker(
        baseline_cls,
        train_scenarios=train_scenarios,
        eval_scenarios=eval_scenarios,
        min_training_samples=64,
        training_batch_size=32,
        train=True,
    )
    current_warm = _evaluate_ranker(
        CurrentRetrievalRanker,
        train_scenarios=train_scenarios,
        eval_scenarios=eval_scenarios,
        min_training_samples=64,
        training_batch_size=32,
        train=True,
    )

    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "config": {
            "seed": args.seed,
            "dim": args.dim,
            "train_per_class": args.train_per_class,
            "eval_per_class": args.eval_per_class,
        },
        "baseline": {
            "cold_start": baseline_cold,
            "warm": baseline_warm,
        },
        "current": {
            "cold_start": current_cold,
            "warm": current_warm,
        },
        "delta": {
            "cold_start": _delta(current_cold, baseline_cold),
            "warm": _delta(current_warm, baseline_warm),
        },
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"Wrote comparison report to {args.output}")
    print(
        "Cold overall delta:",
        payload["delta"]["cold_start"]["overall"],
    )
    print(
        "Warm overall delta:",
        payload["delta"]["warm"]["overall"],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
