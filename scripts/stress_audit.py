from __future__ import annotations

import argparse
import json
import random
import statistics
import string
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from memory_engine.config import EngineConfig
from memory_engine.engine import DecisionEngine
from memory_engine.models.event import Event
from orbit.models import RetrieveRequest
from orbit_api.config import ApiConfig
from orbit_api.service import OrbitApiService


@dataclass(frozen=True)
class ScenarioOutcome:
    name: str
    status: str
    metrics: dict[str, Any]
    findings: list[str]


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return float(values[0])
    ordered = sorted(values)
    position = (len(ordered) - 1) * p
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    blend = position - lower
    return float(ordered[lower] * (1.0 - blend) + ordered[upper] * blend)


def build_engine(
    db_path: Path,
    metrics_path: Path,
    *,
    embedding_dim: int = 64,
    compression_min_count: int = 10_000,
) -> DecisionEngine:
    config = EngineConfig(
        sqlite_path=str(db_path),
        metrics_path=str(metrics_path),
        embedding_dim=embedding_dim,
        persistent_confidence_prior=0.0,
        ephemeral_confidence_prior=0.0,
        compression_min_count=compression_min_count,
    )
    return DecisionEngine(config=config)


def ingest_event(
    engine: DecisionEngine,
    *,
    idx: int,
    entity_id: str,
    event_type: str,
    description: str,
    metadata: dict[str, Any],
) -> str | None:
    event = Event(
        timestamp=1_700_000_000 + idx,
        entity_id=entity_id,
        event_type=event_type,
        description=description,
        metadata=metadata,
    )
    processed = engine.process_input(event)
    decision = engine.make_storage_decision(processed)
    stored = engine.store_memory(processed, decision)
    if stored is None:
        return None
    return stored.memory_id


def random_text(word_count: int, seed: int) -> str:
    rng = random.Random(seed)
    words = [
        "python",
        "loop",
        "function",
        "class",
        "debug",
        "project",
        "scope",
        "async",
        "fastapi",
        "database",
        "testing",
        "memory",
        "ranking",
        "signal",
        "vector",
        "student",
        "lesson",
        "syntax",
        "backend",
        "frontend",
    ]
    return " ".join(rng.choice(words) for _ in range(word_count))


def scenario_throughput_and_scaling(output_dir: Path) -> ScenarioOutcome:
    db_path = output_dir / "throughput_scaling.db"
    metrics_path = output_dir / "throughput_scaling_metrics.json"
    engine = build_engine(db_path, metrics_path, embedding_dim=64, compression_min_count=20_000)
    checkpoints = [1_000, 5_000, 10_000]
    rows: list[dict[str, float | int]] = []
    findings: list[str] = []
    inserted = 0
    ingest_started = time.perf_counter()
    try:
        for checkpoint in checkpoints:
            start = time.perf_counter()
            while inserted < checkpoint:
                idx = inserted + 1
                description = (
                    f"Event {idx}: user asked about python loops and function arguments "
                    f"in module {idx % 17}"
                )
                ingest_event(
                    engine,
                    idx=idx,
                    entity_id=f"user_{idx % 700}",
                    event_type="interaction",
                    description=description,
                    metadata={"intent": "interaction"},
                )
                inserted += 1
            ingest_elapsed = time.perf_counter() - start
            query_latencies_ms: list[float] = []
            for probe in range(50):
                query = (
                    f"python loops function args retrieval probe {probe % 7} "
                    f"user_{probe % 11}"
                )
                probe_start = time.perf_counter()
                engine.retrieve(query=query, top_k=10)
                query_latencies_ms.append((time.perf_counter() - probe_start) * 1000.0)
            row = {
                "memory_count": checkpoint,
                "checkpoint_ingest_sec": round(ingest_elapsed, 4),
                "checkpoint_ingest_eps": round(checkpoint / max(time.perf_counter() - ingest_started, 1e-9), 2),
                "retrieve_p50_ms": round(percentile(query_latencies_ms, 0.50), 3),
                "retrieve_p95_ms": round(percentile(query_latencies_ms, 0.95), 3),
                "retrieve_max_ms": round(max(query_latencies_ms), 3),
            }
            rows.append(row)

        p95_at_10k = rows[-1]["retrieve_p95_ms"]
        if isinstance(p95_at_10k, float) and p95_at_10k > 100.0:
            findings.append(
                f"p95 retrieval latency at 10k memories is {p95_at_10k}ms (>100ms target)."
            )
        if not findings:
            findings.append("Throughput and latency remained within benchmark targets in this run.")
        status = "warn" if any(">" in finding for finding in findings) else "pass"
        return ScenarioOutcome(
            name="throughput_and_scaling",
            status=status,
            metrics={"checkpoints": rows, "final_memory_count": engine.memory_count()},
            findings=findings,
        )
    finally:
        engine.close()


def scenario_storage_bloat(output_dir: Path) -> ScenarioOutcome:
    db_path = output_dir / "storage_bloat.db"
    metrics_path = output_dir / "storage_bloat_metrics.json"
    engine = build_engine(
        db_path,
        metrics_path,
        embedding_dim=384,
        compression_min_count=20_000,
    )
    findings: list[str] = []
    try:
        for idx in range(250):
            payload = (
                "Assistant response: "
                + random_text(900, seed=idx)
                + " "
                + "".join(string.ascii_lowercase[(idx + j) % 26] for j in range(240))
            )
            ingest_event(
                engine,
                idx=idx,
                entity_id="chat_user",
                event_type="assistant_response",
                description=payload,
                metadata={"intent": "assistant_response"},
            )

        records = engine.get_memory(entity_id="chat_user")
        content_lengths = [len(record.content) for record in records]
        summary_lengths = [len(record.summary) for record in records]
        db_size_mb = db_path.stat().st_size / (1024.0 * 1024.0)
        avg_content = statistics.fmean(content_lengths) if content_lengths else 0.0
        avg_summary = statistics.fmean(summary_lengths) if summary_lengths else 0.0
        p95_content = percentile([float(v) for v in content_lengths], 0.95)
        bytes_per_memory = (
            (db_path.stat().st_size / len(records))
            if records
            else 0.0
        )

        assistant_limit = engine.config.assistant_max_content_chars
        if p95_content > assistant_limit + 64:
            findings.append(
                "Assistant payload truncation is ineffective: p95 content length exceeds configured cap."
            )
        if bytes_per_memory > 6_000:
            findings.append(
                "Per-memory footprint remains high; embedding/content storage still needs compaction."
            )
        if not findings:
            findings.append(
                "Assistant payload truncation and compact vector encoding kept storage footprint controlled."
            )
            status = "pass"
        elif any("ineffective" in finding for finding in findings):
            status = "fail"
        else:
            status = "warn"
        return ScenarioOutcome(
            name="storage_bloat_long_assistant_responses",
            status=status,
            metrics={
                "memory_count": len(records),
                "db_size_mb": round(db_size_mb, 3),
                "avg_content_chars": round(avg_content, 1),
                "avg_summary_chars": round(avg_summary, 1),
                "bytes_per_memory": round(bytes_per_memory, 1),
                "p95_content_chars": round(p95_content, 1),
            },
            findings=findings,
        )
    finally:
        engine.close()


def scenario_relevance_and_noise(output_dir: Path) -> ScenarioOutcome:
    db_path = output_dir / "relevance_noise.db"
    metrics_path = output_dir / "relevance_noise_metrics.json"
    engine = build_engine(db_path, metrics_path, embedding_dim=64, compression_min_count=20_000)
    relevant_ids: set[str] = set()
    findings: list[str] = []
    try:
        seed_memories = [
            ("preference_stated", "Alice is a beginner and prefers short analogies."),
            ("preference_stated", "Alice wants concise steps and practical examples."),
            ("learning_progress", "Alice understands loops and basic functions."),
            ("learning_progress", "Alice is moving from beginner to intermediate in FastAPI."),
            ("user_question", "Alice asked about Python scope and function arguments."),
            ("user_question", "Alice asked for real project structure advice."),
        ]
        idx = 0
        for event_type, text in seed_memories:
            memory_id = ingest_event(
                engine,
                idx=idx,
                entity_id="alice",
                event_type=event_type,
                description=text,
                metadata={"intent": event_type},
            )
            if memory_id:
                relevant_ids.add(memory_id)
            idx += 1

        for bot_type in ("general_chatbot", "support_bot", "planning_bot"):
            for j in range(90):
                long_noise = (
                    f"{bot_type} response with broad world knowledge and verbose narrative. "
                    + random_text(160, seed=10_000 + idx + j)
                )
                ingest_event(
                    engine,
                    idx=idx,
                    entity_id="alice",
                    event_type="assistant_response",
                    description=long_noise,
                    metadata={"intent": "assistant_response"},
                )
                idx += 1

        queries = [
            "How should I teach alice python loops based on her style?",
            "What does alice prefer when learning coding topics?",
            "What is alice current coding level and next best topic?",
            "How should explanations be formatted for alice?",
        ]

        precision_values: list[float] = []
        top1_relevant = 0
        assistant_in_top5 = 0
        for query in queries:
            ranked = engine.retrieve(query=query, top_k=5)
            returned_ids = [item.memory.memory_id for item in ranked]
            relevant_hits = sum(1 for memory_id in returned_ids if memory_id in relevant_ids)
            precision = relevant_hits / 5.0
            precision_values.append(precision)
            if returned_ids and returned_ids[0] in relevant_ids:
                top1_relevant += 1
            assistant_in_top5 += sum(
                1 for item in ranked if item.memory.intent == "assistant_response"
            )

        avg_precision = statistics.fmean(precision_values) if precision_values else 0.0
        if avg_precision < 0.6:
            findings.append(
                f"Average precision@5 was {avg_precision:.2f}; noisy assistant memories still dilute top results."
            )
        if assistant_in_top5 > len(queries) * 2:
            findings.append(
                "Assistant-response memories still occupy many top-5 slots under heavy noise."
            )
        if not findings:
            findings.append(
                "Personalization memory stayed dominant under mixed chatbot noise load."
            )
        status = "warn" if findings[0] != "Personalization memory stayed dominant under mixed chatbot noise load." else "pass"
        return ScenarioOutcome(
            name="relevance_vs_noise_multibot",
            status=status,
            metrics={
                "queries_tested": len(queries),
                "avg_precision_at_5": round(avg_precision, 3),
                "top1_relevant_rate": round(top1_relevant / len(queries), 3),
                "assistant_slots_in_top5_total": assistant_in_top5,
                "candidate_memory_count": engine.memory_count(),
            },
            findings=findings,
        )
    finally:
        engine.close()


def scenario_entity_isolation(output_dir: Path) -> ScenarioOutcome:
    db_path = output_dir / "entity_isolation.db"
    metrics_path = output_dir / "entity_isolation_metrics.json"
    engine = build_engine(db_path, metrics_path, embedding_dim=64, compression_min_count=20_000)
    api_config = ApiConfig(
        database_url=f"sqlite:///{db_path.as_posix()}",
        sqlite_fallback_path=str(db_path),
        free_events_per_day=1_000_000,
        free_queries_per_day=1_000_000,
    )
    service = OrbitApiService(api_config=api_config, engine=engine)
    findings: list[str] = []
    try:
        idx = 0
        for person in ("alice", "bob"):
            for n in range(60):
                ingest_event(
                    engine,
                    idx=idx,
                    entity_id=person,
                    event_type="user_question",
                    description=f"{person} message {n} about {person} specific preference",
                    metadata={"intent": "user_question"},
                )
                idx += 1

        alice = service.retrieve(
            RetrieveRequest(
                query="What should I know about alice preferences?",
                entity_id="alice",
                limit=20,
            )
        )
        bob = service.retrieve(
            RetrieveRequest(
                query="What should I know about bob preferences?",
                entity_id="bob",
                limit=20,
            )
        )

        alice_leaks = [
            memory.memory_id
            for memory in alice.memories
            if "alice" not in [str(entity).lower() for entity in memory.metadata.get("entities", [])]
        ]
        bob_leaks = [
            memory.memory_id
            for memory in bob.memories
            if "bob" not in [str(entity).lower() for entity in memory.metadata.get("entities", [])]
        ]
        if alice_leaks or bob_leaks:
            findings.append(
                "Entity-filtered retrieval leaked memories from another entity."
            )
            status = "fail"
        else:
            findings.append("Entity filtering stayed isolated for sampled retrievals.")
            status = "pass"

        return ScenarioOutcome(
            name="entity_isolation_filtering",
            status=status,
            metrics={
                "alice_result_count": len(alice.memories),
                "bob_result_count": len(bob.memories),
                "alice_leak_count": len(alice_leaks),
                "bob_leak_count": len(bob_leaks),
            },
            findings=findings,
        )
    finally:
        service.close()


def scenario_feedback_training(output_dir: Path) -> ScenarioOutcome:
    db_path = output_dir / "feedback_training.db"
    metrics_path = output_dir / "feedback_training_metrics.json"
    engine = build_engine(db_path, metrics_path, embedding_dim=64, compression_min_count=20_000)
    findings: list[str] = []
    try:
        preferred_id = ingest_event(
            engine,
            idx=1,
            entity_id="alice",
            event_type="preference_stated",
            description="Alice prefers concise step-by-step Python explanations.",
            metadata={"intent": "preference_stated"},
        )
        distractor_id = ingest_event(
            engine,
            idx=2,
            entity_id="alice",
            event_type="assistant_response",
            description="Very long historical assistant explanation about many unrelated topics in development and tooling.",
            metadata={"intent": "assistant_response"},
        )
        if preferred_id is None or distractor_id is None:
            return ScenarioOutcome(
                name="feedback_learning_adaptation",
                status="fail",
                metrics={},
                findings=["Failed to store seed memories for feedback test."],
            )

        baseline = engine.retrieve(
            query="How should I explain python to alice?",
            top_k=2,
        )
        baseline_top = baseline[0].memory.memory_id if baseline else ""

        for _ in range(30):
            ranked = engine.retrieve(
                query="How should I explain python to alice?",
                top_k=2,
            )
            ranked_ids = [item.memory.memory_id for item in ranked]
            engine.record_feedback(
                query="How should I explain python to alice?",
                ranked_memory_ids=ranked_ids,
                helpful_memory_ids=[preferred_id],
                outcome_signal=1.0,
            )

        final = engine.retrieve(
            query="How should I explain python to alice?",
            top_k=2,
        )
        final_top = final[0].memory.memory_id if final else ""

        if final_top != preferred_id:
            findings.append("Feedback loop did not converge to preferred memory as top result.")
            status = "warn"
        else:
            findings.append("Feedback loop converged: preferred memory promoted to top.")
            status = "pass"
        return ScenarioOutcome(
            name="feedback_learning_adaptation",
            status=status,
            metrics={
                "baseline_top_memory": baseline_top,
                "final_top_memory": final_top,
                "preferred_memory_id": preferred_id,
            },
            findings=findings,
        )
    finally:
        engine.close()


def scenario_concurrent_ingest_pressure(output_dir: Path) -> ScenarioOutcome:
    db_path = output_dir / "concurrency.db"
    metrics_path = output_dir / "concurrency_metrics.json"
    engine = build_engine(db_path, metrics_path, embedding_dim=64, compression_min_count=20_000)
    findings: list[str] = []
    failures: list[str] = []
    workers = 12
    events_per_worker = 220

    def worker(worker_id: int) -> tuple[int, int]:
        ok = 0
        failed = 0
        for offset in range(events_per_worker):
            idx = (worker_id * events_per_worker) + offset
            try:
                ingest_event(
                    engine,
                    idx=idx,
                    entity_id=f"user_{worker_id}",
                    event_type="interaction",
                    description=f"Concurrent event {idx} for stress write path",
                    metadata={"intent": "interaction"},
                )
                ok += 1
            except Exception:
                failed += 1
        return ok, failed

    started = time.perf_counter()
    try:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(worker, worker_id) for worker_id in range(workers)]
            for future in as_completed(futures):
                try:
                    ok_count, failed_count = future.result()
                    if failed_count:
                        failures.append(f"worker_failed_events={failed_count}")
                except Exception as exc:  # pragma: no cover - stress fallback
                    failures.append(f"worker_exception={type(exc).__name__}:{exc}")
        elapsed = time.perf_counter() - started
        total_target = workers * events_per_worker
        total_stored = engine.memory_count()
        total_failed = sum(
            int(fragment.split("=")[1])
            for fragment in failures
            if fragment.startswith("worker_failed_events=")
        )
        if total_failed > 0:
            findings.append(
                f"Concurrent ingest saw {total_failed} failed writes out of {total_target} attempts."
            )
            status = "fail"
        elif total_stored < total_target:
            findings.append(
                f"Concurrent ingest stored {total_stored}/{total_target} records; potential silent drops."
            )
            status = "warn"
        else:
            findings.append("Concurrent ingest completed with no observed write failures.")
            status = "pass"
        return ScenarioOutcome(
            name="concurrent_ingest_pressure",
            status=status,
            metrics={
                "workers": workers,
                "events_per_worker": events_per_worker,
                "target_events": total_target,
                "stored_events": total_stored,
                "elapsed_sec": round(elapsed, 3),
                "events_per_sec": round(total_target / max(elapsed, 1e-9), 2),
                "failed_events": total_failed,
            },
            findings=findings + failures[:10],
        )
    finally:
        engine.close()


def scenario_compression_behavior(output_dir: Path) -> ScenarioOutcome:
    db_path = output_dir / "compression.db"
    metrics_path = output_dir / "compression_metrics.json"
    engine = build_engine(db_path, metrics_path, embedding_dim=64, compression_min_count=5)
    findings: list[str] = []
    try:
        input_events = 120
        for idx in range(input_events):
            ingest_event(
                engine,
                idx=idx,
                entity_id="repeat_user",
                event_type="assistant_response",
                description=f"Assistant response about topic cluster {idx % 5} and repeated guidance pattern.",
                metadata={"intent": "assistant_response"},
            )

        stored = engine.memory_count()
        records = engine.get_memory(entity_id="repeat_user")
        compressed = [record for record in records if record.is_compressed]
        ratio = 1.0 - (stored / input_events)
        if ratio < 0.5:
            findings.append(
                f"Compression ratio only {ratio:.2f}; repetitive memory compaction weaker than expected."
            )
        else:
            findings.append(f"Compression ratio reached {ratio:.2f} on repetitive traffic.")
        if compressed:
            max_summary = max(len(record.summary) for record in compressed)
            findings.append(f"Largest compressed summary length: {max_summary} chars.")
        return ScenarioOutcome(
            name="compression_behavior",
            status="pass" if ratio >= 0.5 else "warn",
            metrics={
                "input_events": input_events,
                "stored_events": stored,
                "compression_ratio": round(ratio, 3),
                "compressed_records": len(compressed),
            },
            findings=findings,
        )
    finally:
        engine.close()


def write_reports(
    outcomes: list[ScenarioOutcome],
    output_dir: Path,
    started_at: datetime,
    ended_at: datetime,
) -> tuple[Path, Path]:
    summary = {
        "generated_at": ended_at.isoformat(),
        "started_at": started_at.isoformat(),
        "duration_sec": round((ended_at - started_at).total_seconds(), 3),
        "outcomes": [
            {
                "name": item.name,
                "status": item.status,
                "metrics": item.metrics,
                "findings": item.findings,
            }
            for item in outcomes
        ],
    }
    json_path = output_dir / "stress_audit_report.json"
    json_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    lines = [
        "# Orbit Stress Audit Report",
        "",
        f"- Started: `{started_at.isoformat()}`",
        f"- Finished: `{ended_at.isoformat()}`",
        f"- Duration: `{summary['duration_sec']}s`",
        "",
        "## Scenario Results",
        "",
    ]
    for item in outcomes:
        lines.append(f"### {item.name}")
        lines.append(f"- Status: **{item.status.upper()}**")
        lines.append("- Metrics:")
        for key, value in item.metrics.items():
            lines.append(f"  - `{key}`: `{value}`")
        lines.append("- Findings:")
        for finding in item.findings:
            lines.append(f"  - {finding}")
        lines.append("")

    markdown_path = output_dir / "stress_audit_report.md"
    markdown_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, markdown_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run break-oriented Orbit engine stress audit.")
    parser.add_argument(
        "--output-dir",
        default="stress_reports",
        help="Directory where audit report files are written.",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    started = datetime.now(UTC)
    scenarios = [
        scenario_throughput_and_scaling,
        scenario_storage_bloat,
        scenario_relevance_and_noise,
        scenario_entity_isolation,
        scenario_feedback_training,
        scenario_concurrent_ingest_pressure,
        scenario_compression_behavior,
    ]

    outcomes: list[ScenarioOutcome] = []
    for scenario in scenarios:
        scenario_started = time.perf_counter()
        try:
            result = scenario(output_dir)
        except Exception as exc:  # pragma: no cover - fail-safe for stress campaign
            result = ScenarioOutcome(
                name=scenario.__name__,
                status="fail",
                metrics={},
                findings=[f"Scenario crashed: {type(exc).__name__}: {exc}"],
            )
        scenario_elapsed = time.perf_counter() - scenario_started
        result.metrics["scenario_elapsed_sec"] = round(scenario_elapsed, 3)
        outcomes.append(result)

    ended = datetime.now(UTC)
    json_path, markdown_path = write_reports(outcomes, output_dir, started, ended)
    print(f"Wrote {json_path}")
    print(f"Wrote {markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
