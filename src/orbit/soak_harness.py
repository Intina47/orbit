"""Long-horizon personalization soak harness with hard quality gates."""

from __future__ import annotations

import json
import random
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from statistics import fmean
from typing import Any

from memory_engine.config import EngineConfig
from orbit.models import FeedbackRequest, IngestRequest, RetrieveRequest
from orbit_api.config import ApiConfig
from orbit_api.service import OrbitApiService


@dataclass(frozen=True)
class PersonaTrack:
    name: str
    entity_id: str
    style_preference: str
    recurring_error: str
    growth_topic: str
    project_topic: str


@dataclass(frozen=True)
class ProbeSpec:
    probe_id: str
    kind: str
    query_template: str
    expect_inferred: bool = False


@dataclass(frozen=True)
class GateThresholds:
    min_precision_at_5: float = 0.35
    min_top1_relevant_rate: float = 0.65
    max_stale_memory_rate: float = 0.05
    max_assistant_noise_rate: float = 0.20
    min_provenance_type_coverage: float = 0.95
    min_provenance_derived_coverage: float = 0.80


@dataclass(frozen=True)
class GateResult:
    name: str
    comparator: str
    threshold: float
    value: float
    passed: bool


def default_persona_tracks() -> list[PersonaTrack]:
    return [
        PersonaTrack(
            name="alice_novice",
            entity_id="alice",
            style_preference="concise",
            recurring_error="TypeError on list indexing",
            growth_topic="for loops and functions",
            project_topic="modular FastAPI project structure",
        ),
        PersonaTrack(
            name="bruno_debugger",
            entity_id="bruno",
            style_preference="concise",
            recurring_error="variable scope and mutation confusion",
            growth_topic="debugging variable scope",
            project_topic="service layer architecture",
        ),
        PersonaTrack(
            name="carla_builder",
            entity_id="carla",
            style_preference="detailed",
            recurring_error="class initialization and inheritance errors",
            growth_topic="object-oriented design",
            project_topic="Django app architecture",
        ),
        PersonaTrack(
            name="diego_transition",
            entity_id="diego",
            style_preference="detailed",
            recurring_error="async await misuse in handlers",
            growth_topic="async programming patterns",
            project_topic="scalable backend modules",
        ),
    ]


def default_probe_specs() -> list[ProbeSpec]:
    return [
        ProbeSpec(
            probe_id="style",
            kind="style",
            query_template="How should tutoring responses be formatted for {entity_id}?",
            expect_inferred=True,
        ),
        ProbeSpec(
            probe_id="recurring_error",
            kind="error",
            query_template="What mistake does {entity_id} keep repeating in Python?",
            expect_inferred=True,
        ),
        ProbeSpec(
            probe_id="progress",
            kind="progress",
            query_template=(
                "What is {entity_id}'s current level for project architecture and what is next?"
            ),
            expect_inferred=True,
        ),
    ]


def run_soak_campaign(
    *,
    output_dir: Path,
    sqlite_path: Path,
    turns_per_persona: int = 500,
    probe_interval: int = 50,
    embedding_dim: int = 64,
    seed: int = 17,
    thresholds: GateThresholds | None = None,
    persona_tracks: list[PersonaTrack] | None = None,
    probes: list[ProbeSpec] | None = None,
) -> dict[str, Any]:
    if turns_per_persona <= 0:
        msg = "turns_per_persona must be > 0"
        raise ValueError(msg)
    if probe_interval <= 0:
        msg = "probe_interval must be > 0"
        raise ValueError(msg)

    thresholds_value = thresholds or GateThresholds()
    tracks = persona_tracks or default_persona_tracks()
    probe_specs = probes or default_probe_specs()

    output_dir.mkdir(parents=True, exist_ok=True)
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    if sqlite_path.exists():
        sqlite_path.unlink()

    api_config = ApiConfig(
        database_url=f"sqlite:///{sqlite_path.as_posix()}",
        sqlite_fallback_path=str(sqlite_path),
        free_events_per_day=1_000_000,
        free_queries_per_day=1_000_000,
        free_events_per_month=1_000_000,
        free_queries_per_month=1_000_000,
    )
    engine_config = EngineConfig(
        sqlite_path=str(sqlite_path),
        database_url=f"sqlite:///{sqlite_path.as_posix()}",
        embedding_dim=embedding_dim,
        metrics_path=str(output_dir / "soak_metrics.json"),
        compression_min_count=100_000,
        persistent_confidence_prior=0.0,
        ephemeral_confidence_prior=0.0,
        ranker_min_training_samples=2,
        ranker_training_batch_size=2,
        personalization_repeat_threshold=3,
        personalization_similarity_threshold=0.1,
        personalization_lifecycle_check_interval_seconds=0,
    )
    service = OrbitApiService(api_config=api_config, engine_config=engine_config)
    started_at = datetime.now(UTC)
    rng = random.Random(seed)
    event_counts: dict[str, int] = {}
    probe_traces: list[dict[str, Any]] = []
    try:
        for track in tracks:
            _seed_track(service=service, track=track, event_counts=event_counts)

        for turn in range(1, turns_per_persona + 1):
            for track in tracks:
                _simulate_turn(
                    service=service,
                    track=track,
                    turn=turn,
                    rng=rng,
                    event_counts=event_counts,
                )
                if turn % probe_interval == 0:
                    probe_traces.extend(
                        _run_probe_batch(
                            service=service,
                            track=track,
                            turn=turn,
                            probes=probe_specs,
                        )
                    )

        for track in tracks:
            probe_traces.extend(
                _run_probe_batch(
                    service=service,
                    track=track,
                    turn=turns_per_persona,
                    probes=probe_specs,
                )
            )

        metrics = _aggregate_probe_metrics(probe_traces)
        gates, overall_pass = build_gate_matrix(
            metrics=metrics,
            thresholds=thresholds_value,
        )
        failed_traces = [trace for trace in probe_traces if trace["failed_checks"]]
        report = {
            "generated_at": datetime.now(UTC).isoformat(),
            "started_at": started_at.isoformat(),
            "duration_sec": round(
                (datetime.now(UTC) - started_at).total_seconds(),
                3,
            ),
            "config": {
                "turns_per_persona": turns_per_persona,
                "probe_interval": probe_interval,
                "embedding_dim": embedding_dim,
                "seed": seed,
                "persona_count": len(tracks),
                "thresholds": asdict(thresholds_value),
            },
            "dataset": {
                "event_counts": event_counts,
                "total_events": sum(event_counts.values()),
                "total_turns": turns_per_persona * len(tracks),
                "probe_count": len(probe_traces),
            },
            "metrics": metrics,
            "gates": [asdict(item) for item in gates],
            "overall_pass": overall_pass,
            "failed_trace_count": len(failed_traces),
            "failed_traces": failed_traces[:80],
            "probe_traces": probe_traces,
        }
        json_path = output_dir / "personalization_soak_report.json"
        markdown_path = output_dir / "personalization_soak_report.md"
        json_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=True),
            encoding="utf-8",
        )
        markdown_path.write_text(
            render_soak_markdown(report),
            encoding="utf-8",
        )
        report["artifacts"] = {
            "json_path": str(json_path),
            "markdown_path": str(markdown_path),
            "sqlite_path": str(sqlite_path),
        }
        return report
    finally:
        service.close()


def build_gate_matrix(
    *,
    metrics: dict[str, float],
    thresholds: GateThresholds,
) -> tuple[list[GateResult], bool]:
    gates = [
        _gate_gte(
            name="precision_at_5",
            value=metrics["avg_precision_at_5"],
            threshold=thresholds.min_precision_at_5,
        ),
        _gate_gte(
            name="top1_relevant_rate",
            value=metrics["top1_relevant_rate"],
            threshold=thresholds.min_top1_relevant_rate,
        ),
        _gate_lte(
            name="stale_memory_rate",
            value=metrics["stale_memory_rate"],
            threshold=thresholds.max_stale_memory_rate,
        ),
        _gate_lte(
            name="assistant_noise_rate",
            value=metrics["assistant_noise_rate"],
            threshold=thresholds.max_assistant_noise_rate,
        ),
        _gate_gte(
            name="provenance_type_coverage",
            value=metrics["provenance_type_coverage"],
            threshold=thresholds.min_provenance_type_coverage,
        ),
        _gate_gte(
            name="provenance_derived_from_coverage",
            value=metrics["provenance_derived_from_coverage"],
            threshold=thresholds.min_provenance_derived_coverage,
        ),
    ]
    return gates, all(item.passed for item in gates)


def _seed_track(
    *,
    service: OrbitApiService,
    track: PersonaTrack,
    event_counts: dict[str, int],
) -> None:
    seed_events = [
        (
            "preference_stated",
            f"PROFILE_OLD: {track.entity_id} is an absolute beginner in Python.",
        ),
        (
            "preference_stated",
            (
                f"PROFILE: {track.entity_id} prefers "
                f"{'short concise' if track.style_preference == 'concise' else 'detailed step-by-step'} explanations."
            ),
        ),
        (
            "preference_stated",
            (
                f"PREFERENCE: {track.entity_id} prefers project-based learning around "
                f"{track.project_topic}."
            ),
        ),
    ]
    for event_type, content in seed_events:
        service.ingest(
            IngestRequest(
                content=content,
                event_type=event_type,
                entity_id=track.entity_id,
            )
        )
        _increment(event_counts, event_type)


def _simulate_turn(
    *,
    service: OrbitApiService,
    track: PersonaTrack,
    turn: int,
    rng: random.Random,
    event_counts: dict[str, int],
) -> None:
    user_event_type = "user_attempt" if turn % 3 == 0 else "user_question"
    if user_event_type == "user_attempt":
        user_content = (
            f"{track.entity_id} keeps failing with {track.recurring_error} while coding."
        )
    else:
        user_content = (
            f"How can {track.entity_id} improve {track.growth_topic} in real projects?"
        )
    service.ingest(
        IngestRequest(
            content=user_content,
            event_type=user_event_type,
            entity_id=track.entity_id,
        )
    )
    _increment(event_counts, user_event_type)

    if turn % 8 == 0:
        service.ingest(
            IngestRequest(
                content=(
                    f"Assessment passed: {track.entity_id} correctly solved a task about "
                    f"{track.project_topic}."
                ),
                event_type="assessment_result",
                entity_id=track.entity_id,
            )
        )
        _increment(event_counts, "assessment_result")

    if turn % 15 == 0:
        service.ingest(
            IngestRequest(
                content=(
                    f"PROGRESS: {track.entity_id} now understands {track.project_topic}."
                ),
                event_type="learning_progress",
                entity_id=track.entity_id,
            )
        )
        _increment(event_counts, "learning_progress")

    align_with_style = rng.random() >= 0.12
    assistant_content = _assistant_message(track=track, align_with_style=align_with_style)
    assistant = service.ingest(
        IngestRequest(
            content=assistant_content,
            event_type="assistant_response",
            entity_id=track.entity_id,
            metadata={"turn": turn, "style_target": track.style_preference},
        )
    )
    _increment(event_counts, "assistant_response")
    helpful = align_with_style
    service.feedback(
        FeedbackRequest(
            memory_id=assistant.memory_id,
            helpful=helpful,
            outcome_value=1.0 if helpful else -1.0,
        )
    )
    _increment(event_counts, "feedback")


def _assistant_message(*, track: PersonaTrack, align_with_style: bool) -> str:
    concise = (
        f"{track.entity_id}: focus on one fix at a time for {track.recurring_error}. "
        "Use a minimal reproducible snippet and verify each step."
    )
    detailed = (
        f"{track.entity_id}: start by isolating the failing path for {track.recurring_error}. "
        "Then map preconditions, runtime state, and expected outputs. "
        "Document assumptions, write validation checks, and refactor toward modular boundaries "
        f"that match {track.project_topic}. End with regression tests and postmortem notes."
    )
    if track.style_preference == "concise":
        return concise if align_with_style else detailed
    return detailed if align_with_style else concise


def _run_probe_batch(
    *,
    service: OrbitApiService,
    track: PersonaTrack,
    turn: int,
    probes: list[ProbeSpec],
) -> list[dict[str, Any]]:
    traces: list[dict[str, Any]] = []
    for probe in probes:
        query = probe.query_template.format(entity_id=track.entity_id)
        response = service.retrieve(
            RetrieveRequest(
                query=query,
                entity_id=track.entity_id,
                limit=5,
            )
        )
        payload = response.model_dump(mode="json")
        memories = payload["memories"]
        evaluation = _evaluate_probe(
            probe=probe,
            track=track,
            query=query,
            memories=memories,
        )
        traces.append(
            {
                "persona": track.name,
                "entity_id": track.entity_id,
                "turn": turn,
                "probe_id": probe.probe_id,
                "query": query,
                "metrics": evaluation["metrics"],
                "failed_checks": evaluation["failed_checks"],
                "top5": evaluation["top5"],
            }
        )
    return traces


def _evaluate_probe(
    *,
    probe: ProbeSpec,
    track: PersonaTrack,
    query: str,
    memories: list[dict[str, Any]],
) -> dict[str, Any]:
    if not memories:
        return {
            "metrics": {
                "precision_at_5": 0.0,
                "top1_relevant": 0.0,
                "assistant_noise_rate": 0.0,
                "stale_memory_rate": 0.0,
                "inferred_returned_count": 0.0,
                "inferred_with_type_count": 0.0,
                "inferred_with_derived_count": 0.0,
            },
            "failed_checks": ["empty_retrieval_result"],
            "top5": [],
        }

    relevant_hits = 0
    stale_hits = 0
    assistant_hits = 0
    inferred_count = 0
    inferred_with_type = 0
    inferred_with_derived = 0
    top5: list[dict[str, Any]] = []

    for item in memories[:5]:
        metadata = dict(item.get("metadata", {}))
        intent = str(metadata.get("intent", "")).strip().lower()
        content = str(item.get("content", ""))
        if _is_relevant(probe=probe, track=track, intent=intent, content=content):
            relevant_hits += 1
        if _is_stale(content):
            stale_hits += 1
        if intent.startswith("assistant_"):
            assistant_hits += 1
        provenance = dict(metadata.get("inference_provenance", {}))
        is_inferred = bool(provenance.get("is_inferred"))
        if is_inferred:
            inferred_count += 1
            if provenance.get("inference_type"):
                inferred_with_type += 1
            derived_from = provenance.get("derived_from_memory_ids", [])
            if isinstance(derived_from, list) and len(derived_from) > 0:
                inferred_with_derived += 1
        top5.append(
            {
                "memory_id": item.get("memory_id"),
                "intent": intent,
                "score": item.get("rank_score"),
                "content": content,
                "inference_provenance": provenance,
            }
        )

    precision = relevant_hits / float(len(memories[:5]))
    top1_relevant = 1.0 if _is_top1_relevant(probe, track, memories[0]) else 0.0
    assistant_rate = assistant_hits / float(len(memories[:5]))
    stale_rate = stale_hits / float(len(memories[:5]))
    metrics = {
        "precision_at_5": round(precision, 4),
        "top1_relevant": round(top1_relevant, 4),
        "assistant_noise_rate": round(assistant_rate, 4),
        "stale_memory_rate": round(stale_rate, 4),
        "inferred_returned_count": float(inferred_count),
        "inferred_with_type_count": float(inferred_with_type),
        "inferred_with_derived_count": float(inferred_with_derived),
    }
    failed_checks: list[str] = []
    if top1_relevant < 1.0:
        failed_checks.append("top1_not_relevant")
    if probe.kind == "progress" and stale_hits > 0:
        failed_checks.append("stale_memory_present")
    if probe.expect_inferred and inferred_count == 0:
        failed_checks.append("missing_inferred_memory")
    if inferred_count > 0 and inferred_with_type < inferred_count:
        failed_checks.append("missing_inference_type")
    if inferred_count > 0 and inferred_with_derived < inferred_count:
        failed_checks.append("missing_derived_from")
    return {
        "metrics": metrics,
        "failed_checks": failed_checks,
        "top5": top5,
    }


def _aggregate_probe_metrics(probe_traces: list[dict[str, Any]]) -> dict[str, float]:
    if not probe_traces:
        return {
            "avg_precision_at_5": 0.0,
            "top1_relevant_rate": 0.0,
            "assistant_noise_rate": 0.0,
            "stale_memory_rate": 0.0,
            "provenance_type_coverage": 0.0,
            "provenance_derived_from_coverage": 0.0,
            "inferred_returned_count": 0.0,
            "query_count": 0.0,
        }

    precision_values = [trace["metrics"]["precision_at_5"] for trace in probe_traces]
    top1_values = [trace["metrics"]["top1_relevant"] for trace in probe_traces]
    assistant_values = [
        trace["metrics"]["assistant_noise_rate"] for trace in probe_traces
    ]
    stale_values = [trace["metrics"]["stale_memory_rate"] for trace in probe_traces]

    inferred_returned = sum(
        trace["metrics"]["inferred_returned_count"] for trace in probe_traces
    )
    inferred_with_type = sum(
        trace["metrics"]["inferred_with_type_count"] for trace in probe_traces
    )
    inferred_with_derived = sum(
        trace["metrics"]["inferred_with_derived_count"] for trace in probe_traces
    )
    if inferred_returned > 0:
        type_coverage = inferred_with_type / inferred_returned
        derived_coverage = inferred_with_derived / inferred_returned
    else:
        type_coverage = 0.0
        derived_coverage = 0.0

    return {
        "avg_precision_at_5": round(fmean(precision_values), 4),
        "top1_relevant_rate": round(fmean(top1_values), 4),
        "assistant_noise_rate": round(fmean(assistant_values), 4),
        "stale_memory_rate": round(fmean(stale_values), 4),
        "provenance_type_coverage": round(type_coverage, 4),
        "provenance_derived_from_coverage": round(derived_coverage, 4),
        "inferred_returned_count": float(inferred_returned),
        "query_count": float(len(probe_traces)),
    }


def render_soak_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Orbit Personalization Soak Report",
        "",
        f"- Generated at: `{report['generated_at']}`",
        f"- Duration: `{report['duration_sec']}s`",
        f"- Overall pass: `{report['overall_pass']}`",
        f"- Failed traces: `{report['failed_trace_count']}`",
        "",
        "## Gate Matrix",
        "",
        "| Gate | Comparator | Threshold | Value | Pass |",
        "| --- | --- | ---: | ---: | --- |",
    ]
    for gate in report.get("gates", []):
        lines.append(
            f"| {gate['name']} | {gate['comparator']} | "
            f"{gate['threshold']:.3f} | {gate['value']:.3f} | {gate['passed']} |"
        )
    lines.extend(
        [
            "",
            "## Metrics",
            "",
        ]
    )
    metrics = report.get("metrics", {})
    for key in sorted(metrics):
        lines.append(f"- `{key}`: `{metrics[key]}`")
    lines.extend(
        [
            "",
            "## Failed Traces",
            "",
        ]
    )
    failed = report.get("failed_traces", [])
    if not failed:
        lines.append("- None")
    else:
        for trace in failed:
            lines.append(
                f"### {trace['persona']} :: {trace['probe_id']} (turn {trace['turn']})"
            )
            lines.append(f"- Query: `{trace['query']}`")
            lines.append(f"- Failed checks: `{', '.join(trace['failed_checks'])}`")
            lines.append(f"- Metrics: `{json.dumps(trace['metrics'], ensure_ascii=True)}`")
            lines.append("- Top 5:")
            for item in trace.get("top5", []):
                lines.append(
                    f"  - `{item['intent']}` score={item['score']} "
                    f"memory_id={item['memory_id']} content={item['content']}"
                )
                lines.append(
                    "    provenance="
                    + json.dumps(item.get("inference_provenance", {}), ensure_ascii=True)
                )
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _gate_gte(name: str, value: float, threshold: float) -> GateResult:
    return GateResult(
        name=name,
        comparator=">=",
        threshold=threshold,
        value=value,
        passed=value >= threshold,
    )


def _gate_lte(name: str, value: float, threshold: float) -> GateResult:
    return GateResult(
        name=name,
        comparator="<=",
        threshold=threshold,
        value=value,
        passed=value <= threshold,
    )


def _is_top1_relevant(probe: ProbeSpec, track: PersonaTrack, item: dict[str, Any]) -> bool:
    metadata = dict(item.get("metadata", {}))
    intent = str(metadata.get("intent", "")).strip().lower()
    content = str(item.get("content", ""))
    return _is_relevant(probe=probe, track=track, intent=intent, content=content)


def _is_relevant(
    *,
    probe: ProbeSpec,
    track: PersonaTrack,
    intent: str,
    content: str,
) -> bool:
    normalized_content = content.lower()
    if probe.kind == "style":
        if intent not in {"preference_stated", "inferred_preference"}:
            return False
        if track.style_preference == "concise":
            return "concise" in normalized_content or "short" in normalized_content
        return "detailed" in normalized_content or "fuller context" in normalized_content

    if probe.kind == "error":
        if intent not in {"inferred_learning_pattern", "user_attempt"}:
            return False
        error_tokens = _tokens(track.recurring_error)
        return len(_tokens(content).intersection(error_tokens)) >= 2

    if probe.kind == "progress":
        if intent != "learning_progress":
            return False
        if "profile_old" in normalized_content or "absolute beginner" in normalized_content:
            return False
        progress_tokens = _tokens(track.project_topic)
        return len(_tokens(content).intersection(progress_tokens)) >= 1

    return False


def _is_stale(content: str) -> bool:
    normalized = content.lower()
    stale_markers = (
        "profile_old",
        "absolute beginner",
        "novice",
        "new to coding",
        "entry level",
        "newbie",
    )
    return any(marker in normalized for marker in stale_markers)


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _increment(counter: dict[str, int], key: str) -> None:
    counter[key] = counter.get(key, 0) + 1
