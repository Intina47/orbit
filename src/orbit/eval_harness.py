"""Baseline-vs-Orbit personalization evaluation harness."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from statistics import fmean
from typing import Any

from memory_engine.config import EngineConfig
from orbit.models import FeedbackRequest, IngestRequest, RetrieveRequest
from orbit_api.config import ApiConfig
from orbit_api.service import OrbitApiService

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class EvalRecord:
    content: str
    event_type: str
    entity_id: str
    order: int


@dataclass(frozen=True)
class EvalQuery:
    query_id: str
    query: str
    entity_id: str
    relevant_contents: frozenset[str]
    stale_contents: frozenset[str]


@dataclass(frozen=True)
class RankedItem:
    content: str
    event_type: str
    score: float


@dataclass(frozen=True)
class QueryScore:
    precision_at_5: float
    top1_relevant: float
    personalization_hit: float
    assistant_noise_rate: float
    stale_memory_rate: float
    predicted_helpful: float


def run_evaluation(
    *,
    output_dir: Path,
    sqlite_path: Path,
    embedding_dim: int = 64,
    assistant_noise_events: int = 90,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)

    if sqlite_path.exists():
        sqlite_path.unlink()

    api_config = ApiConfig(
        database_url=f"sqlite:///{sqlite_path.as_posix()}",
        sqlite_fallback_path=str(sqlite_path),
        free_events_per_day=1_000_000,
        free_queries_per_day=1_000_000,
    )
    engine_config = EngineConfig(
        sqlite_path=str(sqlite_path),
        database_url=f"sqlite:///{sqlite_path.as_posix()}",
        embedding_dim=embedding_dim,
        metrics_path=str(output_dir / "orbit_eval_metrics.json"),
        compression_min_count=10_000,
        persistent_confidence_prior=0.0,
        ephemeral_confidence_prior=0.0,
        ranker_min_training_samples=4,
        ranker_training_batch_size=4,
    )
    service = OrbitApiService(api_config=api_config, engine_config=engine_config)
    started_at = datetime.now(UTC)
    try:
        dataset = build_reference_dataset(assistant_noise_events=assistant_noise_events)
        content_to_memory_id = _ingest_dataset(service=service, records=dataset["records"])
        _apply_feedback_priors(
            service=service,
            content_to_memory_id=content_to_memory_id,
            positive_contents=dataset["positive_feedback_contents"],
            negative_contents=dataset["negative_feedback_contents"],
        )

        queries = dataset["queries"]
        baseline_result = run_baseline_strategy(records=dataset["records"], queries=queries)
        orbit_result = run_orbit_strategy(service=service, queries=queries)

        report = build_scorecard(
            dataset_records=dataset["records"],
            queries=queries,
            baseline_result=baseline_result,
            orbit_result=orbit_result,
            started_at=started_at,
            ended_at=datetime.now(UTC),
        )

        json_path = output_dir / "orbit_eval_scorecard.json"
        md_path = output_dir / "orbit_eval_scorecard.md"
        json_path.write_text(json.dumps(report, indent=2, ensure_ascii=True), encoding="utf-8")
        md_path.write_text(render_markdown_report(report), encoding="utf-8")
        report["artifacts"] = {
            "json_path": str(json_path),
            "markdown_path": str(md_path),
            "sqlite_path": str(sqlite_path),
        }
        return report
    finally:
        service.close()


def build_reference_dataset(*, assistant_noise_events: int) -> dict[str, Any]:
    beginner = "PROFILE: Alice is an absolute beginner in Python."
    analogies = "PROFILE: Alice learns best with analogies and simple metaphors."
    short_explanations = "PROFILE: Alice prefers short explanations with tiny code snippets."
    scope_gap = "PROFILE: Alice has not learned variable scope yet."
    old_beginner = "PROFILE_OLD: Alice said she was a beginner about a month ago."
    progress_loops = "PROGRESS: Alice completed loops and functions lessons."
    progress_oop = "PROGRESS: Alice now understands classes and basic OOP."
    project_pref = "PREFERENCE: Alice prefers project-based learning over abstract drills."
    repeated_mistake = (
        "PATTERN: Alice repeatedly confuses list mutation and reassignment semantics."
    )

    records: list[EvalRecord] = []
    order = 0

    def append(entity_id: str, event_type: str, content: str) -> None:
        nonlocal order
        records.append(
            EvalRecord(
                content=content,
                event_type=event_type,
                entity_id=entity_id,
                order=order,
            )
        )
        order += 1

    append("alice", "preference_stated", old_beginner)
    append("alice", "preference_stated", beginner)
    append("alice", "preference_stated", analogies)
    append("alice", "preference_stated", short_explanations)
    append("alice", "learning_progress", scope_gap)
    append("alice", "learning_progress", progress_loops)
    append("alice", "learning_progress", progress_oop)
    append("alice", "preference_stated", project_pref)
    append("alice", "inferred_learning_pattern", repeated_mistake)

    for idx in range(assistant_noise_events):
        append(
            "alice",
            "assistant_response",
            (
                f"ASSISTANT_LONG: Generic coding answer #{idx}. "
                "This long response mentions python loops classes project architecture "
                "beginner advanced debugging for-loop while-loop variable scope and many extras. "
                * 3
            ).strip(),
        )

    for idx in range(45):
        append(
            "bob",
            "assistant_response",
            (
                f"ASSISTANT_LONG: Bob noise #{idx}. "
                "Python projects and architecture discussion unrelated to Alice."
            ),
        )
    for idx in range(30):
        append(
            "carol",
            "user_question",
            f"Carol asked question #{idx} about JavaScript modules and React patterns.",
        )

    queries = [
        EvalQuery(
            query_id="day1_loops",
            query="How should I explain for loops to Alice right now?",
            entity_id="alice",
            relevant_contents=frozenset(
                {beginner, analogies, short_explanations, scope_gap}
            ),
            stale_contents=frozenset({old_beginner}),
        ),
        EvalQuery(
            query_id="day30_architecture",
            query=(
                "Alice now asks about structuring larger Python projects. "
                "What context should guide the response?"
            ),
            entity_id="alice",
            relevant_contents=frozenset({progress_loops, progress_oop, project_pref}),
            stale_contents=frozenset({old_beginner}),
        ),
        EvalQuery(
            query_id="recurring_error",
            query="What mistake does Alice keep repeating when coding in Python?",
            entity_id="alice",
            relevant_contents=frozenset({repeated_mistake}),
            stale_contents=frozenset(),
        ),
        EvalQuery(
            query_id="teaching_style",
            query="How should tutoring responses be formatted for Alice?",
            entity_id="alice",
            relevant_contents=frozenset({analogies, short_explanations}),
            stale_contents=frozenset({old_beginner}),
        ),
    ]

    return {
        "records": records,
        "queries": queries,
        "positive_feedback_contents": [
            beginner,
            analogies,
            short_explanations,
            progress_loops,
            progress_oop,
            project_pref,
            repeated_mistake,
        ],
        "negative_feedback_contents": [
            old_beginner,
            *[
                item.content
                for item in records
                if item.event_type == "assistant_response" and item.entity_id == "alice"
            ][:4],
        ],
    }


def run_baseline_strategy(
    *,
    records: list[EvalRecord],
    queries: list[EvalQuery],
) -> dict[str, Any]:
    traces: list[dict[str, Any]] = []
    query_scores: list[QueryScore] = []

    for query in queries:
        candidates = [item for item in records if item.entity_id == query.entity_id]
        ranked = sorted(
            (
                RankedItem(
                    content=item.content,
                    event_type=item.event_type,
                    score=baseline_score(query=query.query, record=item, total=len(candidates)),
                )
                for item in candidates
            ),
            key=lambda item: item.score,
            reverse=True,
        )[:5]
        query_score = evaluate_ranking(query=query, ranked=ranked)
        query_scores.append(query_score)
        traces.append(trace_for_query(strategy="baseline", query=query, ranked=ranked, score=query_score))

    return {
        "metrics": aggregate_query_scores(query_scores),
        "query_traces": traces,
    }


def run_orbit_strategy(
    *,
    service: OrbitApiService,
    queries: list[EvalQuery],
) -> dict[str, Any]:
    traces: list[dict[str, Any]] = []
    query_scores: list[QueryScore] = []

    for query in queries:
        response = service.retrieve(
            RetrieveRequest(
                query=query.query,
                entity_id=query.entity_id,
                limit=5,
            )
        )
        ranked = [
            RankedItem(
                content=memory.content,
                event_type=str(memory.metadata.get("intent", "")),
                score=float(memory.rank_score),
            )
            for memory in response.memories
        ]
        query_score = evaluate_ranking(query=query, ranked=ranked)
        query_scores.append(query_score)
        traces.append(trace_for_query(strategy="orbit", query=query, ranked=ranked, score=query_score))

    return {
        "metrics": aggregate_query_scores(query_scores),
        "query_traces": traces,
    }


def build_scorecard(
    *,
    dataset_records: list[EvalRecord],
    queries: list[EvalQuery],
    baseline_result: dict[str, Any],
    orbit_result: dict[str, Any],
    started_at: datetime,
    ended_at: datetime,
) -> dict[str, Any]:
    baseline_metrics = baseline_result["metrics"]
    orbit_metrics = orbit_result["metrics"]
    return {
        "generated_at": ended_at.isoformat(),
        "started_at": started_at.isoformat(),
        "duration_sec": round((ended_at - started_at).total_seconds(), 3),
        "dataset": {
            "total_records": len(dataset_records),
            "entity_counts": _group_counts([item.entity_id for item in dataset_records]),
            "event_type_counts": _group_counts([item.event_type for item in dataset_records]),
            "query_count": len(queries),
        },
        "metrics": {
            "baseline": baseline_metrics,
            "orbit": orbit_metrics,
        },
        "lift": {
            "precision_at_5_delta": round(
                orbit_metrics["avg_precision_at_5"] - baseline_metrics["avg_precision_at_5"], 3
            ),
            "top1_relevant_rate_delta": round(
                orbit_metrics["top1_relevant_rate"] - baseline_metrics["top1_relevant_rate"], 3
            ),
            "personalization_hit_rate_delta": round(
                orbit_metrics["personalization_hit_rate"]
                - baseline_metrics["personalization_hit_rate"],
                3,
            ),
            "predicted_helpfulness_delta": round(
                orbit_metrics["predicted_helpfulness_rate"]
                - baseline_metrics["predicted_helpfulness_rate"],
                3,
            ),
            "assistant_noise_rate_delta": round(
                orbit_metrics["assistant_noise_rate"] - baseline_metrics["assistant_noise_rate"],
                3,
            ),
            "stale_memory_rate_delta": round(
                orbit_metrics["stale_memory_rate"] - baseline_metrics["stale_memory_rate"],
                3,
            ),
        },
        "query_traces": baseline_result["query_traces"] + orbit_result["query_traces"],
    }


def tokenize(value: str) -> set[str]:
    return set(_TOKEN_PATTERN.findall(value.lower()))


def baseline_score(*, query: str, record: EvalRecord, total: int) -> float:
    query_tokens = tokenize(query)
    content_tokens = tokenize(record.content)
    overlap = 0.0
    if query_tokens:
        overlap = len(query_tokens & content_tokens) / float(len(query_tokens))
    length_bias = 0.0
    intent_prior = 0.0
    if record.event_type == "assistant_response":
        length_bias = min(len(record.content) / 800.0, 1.0) * 0.09
        intent_prior -= 0.03
    elif record.event_type in {
        "preference_stated",
        "learning_progress",
        "inferred_learning_pattern",
    }:
        intent_prior += 0.08
    recency_bonus = (record.order / max(total, 1)) * 0.08
    return overlap + length_bias + recency_bonus + intent_prior


def evaluate_ranking(*, query: EvalQuery, ranked: list[RankedItem]) -> QueryScore:
    if not ranked:
        return QueryScore(
            precision_at_5=0.0,
            top1_relevant=0.0,
            personalization_hit=0.0,
            assistant_noise_rate=0.0,
            stale_memory_rate=0.0,
            predicted_helpful=0.0,
        )
    relevant_hits = sum(1 for item in ranked if item.content in query.relevant_contents)
    stale_hits = sum(1 for item in ranked if item.content in query.stale_contents)
    assistant_hits = sum(1 for item in ranked if item.event_type == "assistant_response")
    top1_relevant = 1.0 if ranked[0].content in query.relevant_contents else 0.0
    personalization_hit = 1.0 if relevant_hits > 0 else 0.0
    precision = relevant_hits / float(len(ranked))
    assistant_rate = assistant_hits / float(len(ranked))
    stale_rate = stale_hits / float(len(ranked))
    helpful_score = (
        (1.0 if top1_relevant > 0 else 0.0)
        + (1.0 if relevant_hits >= 2 else 0.0)
        - (1.0 if assistant_hits >= 3 else 0.0)
        - (1.0 if stale_hits > 0 else 0.0)
    )
    return QueryScore(
        precision_at_5=precision,
        top1_relevant=top1_relevant,
        personalization_hit=personalization_hit,
        assistant_noise_rate=assistant_rate,
        stale_memory_rate=stale_rate,
        predicted_helpful=1.0 if helpful_score >= 1.0 else 0.0,
    )


def aggregate_query_scores(scores: list[QueryScore]) -> dict[str, float]:
    if not scores:
        return {
            "avg_precision_at_5": 0.0,
            "top1_relevant_rate": 0.0,
            "personalization_hit_rate": 0.0,
            "assistant_noise_rate": 0.0,
            "stale_memory_rate": 0.0,
            "predicted_helpfulness_rate": 0.0,
        }
    return {
        "avg_precision_at_5": round(fmean(item.precision_at_5 for item in scores), 3),
        "top1_relevant_rate": round(fmean(item.top1_relevant for item in scores), 3),
        "personalization_hit_rate": round(fmean(item.personalization_hit for item in scores), 3),
        "assistant_noise_rate": round(fmean(item.assistant_noise_rate for item in scores), 3),
        "stale_memory_rate": round(fmean(item.stale_memory_rate for item in scores), 3),
        "predicted_helpfulness_rate": round(fmean(item.predicted_helpful for item in scores), 3),
    }


def trace_for_query(
    *,
    strategy: str,
    query: EvalQuery,
    ranked: list[RankedItem],
    score: QueryScore,
) -> dict[str, Any]:
    return {
        "strategy": strategy,
        "query_id": query.query_id,
        "query": query.query,
        "metrics": {
            "precision_at_5": round(score.precision_at_5, 3),
            "top1_relevant": round(score.top1_relevant, 3),
            "personalization_hit": round(score.personalization_hit, 3),
            "assistant_noise_rate": round(score.assistant_noise_rate, 3),
            "stale_memory_rate": round(score.stale_memory_rate, 3),
            "predicted_helpful": round(score.predicted_helpful, 3),
        },
        "top5": [
            {
                "rank": index + 1,
                "event_type": item.event_type,
                "score": round(item.score, 4),
                "content": item.content,
            }
            for index, item in enumerate(ranked[:5])
        ],
    }


def render_markdown_report(report: dict[str, Any]) -> str:
    metrics = report["metrics"]
    lift = report["lift"]
    lines = [
        "# Orbit Evaluation Scorecard",
        "",
        f"- Generated at: `{report['generated_at']}`",
        f"- Duration: `{report['duration_sec']}s`",
        f"- Dataset records: `{report['dataset']['total_records']}`",
        f"- Queries: `{report['dataset']['query_count']}`",
        "",
        "## Metrics",
        "",
        "| Metric | Baseline | Orbit | Delta |",
        "| --- | ---: | ---: | ---: |",
        (
            f"| Precision@5 | {metrics['baseline']['avg_precision_at_5']:.3f} "
            f"| {metrics['orbit']['avg_precision_at_5']:.3f} "
            f"| {lift['precision_at_5_delta']:+.3f} |"
        ),
        (
            f"| Top1 relevant rate | {metrics['baseline']['top1_relevant_rate']:.3f} "
            f"| {metrics['orbit']['top1_relevant_rate']:.3f} "
            f"| {lift['top1_relevant_rate_delta']:+.3f} |"
        ),
        (
            f"| Personalization hit rate | {metrics['baseline']['personalization_hit_rate']:.3f} "
            f"| {metrics['orbit']['personalization_hit_rate']:.3f} "
            f"| {lift['personalization_hit_rate_delta']:+.3f} |"
        ),
        (
            f"| Predicted helpfulness rate | {metrics['baseline']['predicted_helpfulness_rate']:.3f} "
            f"| {metrics['orbit']['predicted_helpfulness_rate']:.3f} "
            f"| {lift['predicted_helpfulness_delta']:+.3f} |"
        ),
        (
            f"| Assistant noise rate | {metrics['baseline']['assistant_noise_rate']:.3f} "
            f"| {metrics['orbit']['assistant_noise_rate']:.3f} "
            f"| {lift['assistant_noise_rate_delta']:+.3f} |"
        ),
        (
            f"| Stale memory rate | {metrics['baseline']['stale_memory_rate']:.3f} "
            f"| {metrics['orbit']['stale_memory_rate']:.3f} "
            f"| {lift['stale_memory_rate_delta']:+.3f} |"
        ),
        "",
        "## Query Traces",
        "",
    ]
    for trace in report["query_traces"]:
        lines.append(f"### {trace['strategy']} :: {trace['query_id']}")
        lines.append("")
        lines.append(f"- Query: `{trace['query']}`")
        lines.append(f"- Precision@5: `{trace['metrics']['precision_at_5']}`")
        lines.append("| Rank | Event Type | Score | Content |")
        lines.append("| ---: | --- | ---: | --- |")
        for row in trace["top5"]:
            content = row["content"].replace("|", "\\|")
            lines.append(
                f"| {row['rank']} | {row['event_type']} | {row['score']:.4f} | {content} |"
            )
        lines.append("")
    return "\n".join(lines) + "\n"


def _ingest_dataset(
    *,
    service: OrbitApiService,
    records: list[EvalRecord],
) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for item in records:
        response = service.ingest(
            IngestRequest(
                content=item.content,
                event_type=item.event_type,
                entity_id=item.entity_id,
                metadata={"seed_order": item.order},
            )
        )
        mapping[item.content] = response.memory_id
    return mapping


def _apply_feedback_priors(
    *,
    service: OrbitApiService,
    content_to_memory_id: dict[str, str],
    positive_contents: list[str],
    negative_contents: list[str],
) -> None:
    for _ in range(2):
        for content in positive_contents:
            memory_id = content_to_memory_id.get(content)
            if memory_id is None:
                continue
            service.feedback(
                FeedbackRequest(memory_id=memory_id, helpful=True, outcome_value=1.0)
            )
        for content in negative_contents:
            memory_id = content_to_memory_id.get(content)
            if memory_id is None:
                continue
            service.feedback(
                FeedbackRequest(memory_id=memory_id, helpful=False, outcome_value=-1.0)
            )


def _group_counts(values: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in values:
        counts[item] = counts.get(item, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: kv[0]))
