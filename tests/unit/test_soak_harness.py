from __future__ import annotations

from pathlib import Path

from orbit.soak_harness import (
    GateThresholds,
    PersonaTrack,
    ProbeSpec,
    build_gate_matrix,
    run_soak_campaign,
)


def test_build_gate_matrix_detects_failures() -> None:
    metrics = {
        "avg_precision_at_5": 0.2,
        "top1_relevant_rate": 0.3,
        "assistant_noise_rate": 0.4,
        "stale_memory_rate": 0.1,
        "provenance_type_coverage": 0.5,
        "provenance_derived_from_coverage": 0.2,
        "inferred_returned_count": 2.0,
        "query_count": 8.0,
    }
    gates, overall = build_gate_matrix(metrics=metrics, thresholds=GateThresholds())
    assert overall is False
    failing = [gate.name for gate in gates if not gate.passed]
    assert "precision_at_5" in failing
    assert "top1_relevant_rate" in failing
    assert "assistant_noise_rate" in failing
    assert "stale_memory_rate" in failing
    assert "provenance_type_coverage" in failing
    assert "provenance_derived_from_coverage" in failing


def test_run_soak_campaign_writes_artifacts(tmp_path: Path) -> None:
    output_dir = tmp_path / "soak"
    sqlite_path = tmp_path / "soak.db"
    persona = PersonaTrack(
        name="tiny",
        entity_id="tiny",
        style_preference="concise",
        recurring_error="TypeError on list indexing",
        growth_topic="for loops",
        project_topic="module architecture",
    )
    probes = [
        ProbeSpec(
            probe_id="error",
            kind="error",
            query_template="What mistake does {entity_id} keep repeating in Python?",
            expect_inferred=True,
        )
    ]
    report = run_soak_campaign(
        output_dir=output_dir,
        sqlite_path=sqlite_path,
        turns_per_persona=12,
        probe_interval=6,
        embedding_dim=32,
        seed=1,
        thresholds=GateThresholds(
            min_precision_at_5=0.0,
            min_top1_relevant_rate=0.0,
            max_stale_memory_rate=1.0,
            max_assistant_noise_rate=1.0,
            min_provenance_type_coverage=0.0,
            min_provenance_derived_coverage=0.0,
        ),
        persona_tracks=[persona],
        probes=probes,
    )
    artifacts = report.get("artifacts", {})
    json_path = Path(str(artifacts.get("json_path", "")))
    markdown_path = Path(str(artifacts.get("markdown_path", "")))
    assert json_path.exists()
    assert markdown_path.exists()
    assert report["dataset"]["probe_count"] >= 2
    assert "gates" in report
    assert "metrics" in report
