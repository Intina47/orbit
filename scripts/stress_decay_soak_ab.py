from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _load_baseline_ranker_class() -> type[Any]:
    source = subprocess.check_output(
        ["git", "show", "HEAD:src/decision_engine/retrieval_ranker.py"],
        text=True,
    )
    with tempfile.TemporaryDirectory(prefix="orbit-ranker-soak-baseline-") as tmp_dir:
        path = Path(tmp_dir) / "baseline_ranker.py"
        path.write_text(source, encoding="utf-8")
        spec = importlib.util.spec_from_file_location("baseline_ranker_soak", path)
        if spec is None or spec.loader is None:
            msg = "failed to load baseline ranker module"
            raise RuntimeError(msg)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        cls = getattr(module, "RetrievalRanker", None)
        if cls is None:
            msg = "baseline RetrievalRanker class not found"
            raise RuntimeError(msg)
        return cls


def _run_soak_with_ranker(
    *,
    ranker_cls: type[Any],
    output_dir: Path,
    sqlite_path: Path,
    turns_per_persona: int,
    probe_interval: int,
    seed: int,
) -> dict[str, Any]:
    import decision_engine.retrieval_ranker as rr_module
    import memory_engine.engine as engine_module
    from orbit.soak_harness import run_soak_campaign

    rr_module.RetrievalRanker = ranker_cls
    engine_module.RetrievalRanker = ranker_cls

    return run_soak_campaign(
        output_dir=output_dir,
        sqlite_path=sqlite_path,
        turns_per_persona=turns_per_persona,
        probe_interval=probe_interval,
        embedding_dim=64,
        seed=seed,
    )


def _metric_slice(report: dict[str, Any]) -> dict[str, float]:
    metrics = report["metrics"]
    keys = (
        "avg_precision_at_5",
        "top1_relevant_rate",
        "assistant_noise_rate",
        "stale_memory_rate",
        "provenance_type_coverage",
        "provenance_derived_from_coverage",
        "inferred_returned_count",
    )
    return {key: float(metrics[key]) for key in keys}


def _delta(current: dict[str, float], baseline: dict[str, float]) -> dict[str, float]:
    return {key: current[key] - baseline[key] for key in current.keys()}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run personalization soak A/B for current vs baseline decay ranker."
    )
    parser.add_argument("--turns-per-persona", type=int, default=160)
    parser.add_argument("--probe-interval", type=int, default=20)
    parser.add_argument("--seed", type=int, default=19)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("quality_reports/decay_soak_ab.json"),
    )
    args = parser.parse_args()

    baseline_cls = _load_baseline_ranker_class()

    baseline_report = _run_soak_with_ranker(
        ranker_cls=baseline_cls,
        output_dir=Path("quality_reports/decay_soak_baseline"),
        sqlite_path=Path("tmp/decay_soak_baseline.db"),
        turns_per_persona=args.turns_per_persona,
        probe_interval=args.probe_interval,
        seed=args.seed,
    )

    from decision_engine.retrieval_ranker import RetrievalRanker as current_ranker_cls

    current_report = _run_soak_with_ranker(
        ranker_cls=current_ranker_cls,
        output_dir=Path("quality_reports/decay_soak_current"),
        sqlite_path=Path("tmp/decay_soak_current.db"),
        turns_per_persona=args.turns_per_persona,
        probe_interval=args.probe_interval,
        seed=args.seed,
    )

    baseline_metrics = _metric_slice(baseline_report)
    current_metrics = _metric_slice(current_report)
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "config": {
            "turns_per_persona": args.turns_per_persona,
            "probe_interval": args.probe_interval,
            "seed": args.seed,
        },
        "baseline": {
            "metrics": baseline_metrics,
            "overall_pass": bool(baseline_report["overall_pass"]),
            "failed_trace_count": int(baseline_report["failed_trace_count"]),
        },
        "current": {
            "metrics": current_metrics,
            "overall_pass": bool(current_report["overall_pass"]),
            "failed_trace_count": int(current_report["failed_trace_count"]),
        },
        "delta_current_minus_baseline": _delta(current_metrics, baseline_metrics),
        "artifacts": {
            "baseline_json": "quality_reports/decay_soak_baseline/personalization_soak_report.json",
            "current_json": "quality_reports/decay_soak_current/personalization_soak_report.json",
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote soak A/B report to {args.output}")
    print("Delta:", payload["delta_current_minus_baseline"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
