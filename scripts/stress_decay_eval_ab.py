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
    with tempfile.TemporaryDirectory(prefix="orbit-ranker-eval-baseline-") as tmp_dir:
        path = Path(tmp_dir) / "baseline_ranker.py"
        path.write_text(source, encoding="utf-8")
        spec = importlib.util.spec_from_file_location("baseline_ranker_eval", path)
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


def _run_eval_with_ranker(
    *,
    ranker_cls: type[Any],
    output_dir: Path,
    sqlite_path: Path,
    assistant_noise_events: int,
) -> dict[str, Any]:
    import decision_engine.retrieval_ranker as rr_module
    import memory_engine.engine as engine_module
    from orbit.eval_harness import run_evaluation

    # Patch both module-level references used by engine wiring.
    rr_module.RetrievalRanker = ranker_cls
    engine_module.RetrievalRanker = ranker_cls

    report = run_evaluation(
        output_dir=output_dir,
        sqlite_path=sqlite_path,
        embedding_dim=64,
        assistant_noise_events=assistant_noise_events,
    )
    return report


def _metric_slice(report: dict[str, Any]) -> dict[str, float]:
    orbit = report["metrics"]["orbit"]
    return {
        "avg_precision_at_5": float(orbit["avg_precision_at_5"]),
        "top1_relevant_rate": float(orbit["top1_relevant_rate"]),
        "personalization_hit_rate": float(orbit["personalization_hit_rate"]),
        "assistant_noise_rate": float(orbit["assistant_noise_rate"]),
        "stale_memory_rate": float(orbit["stale_memory_rate"]),
        "predicted_helpfulness_rate": float(orbit["predicted_helpfulness_rate"]),
    }


def _delta(current: dict[str, float], baseline: dict[str, float]) -> dict[str, float]:
    return {key: current[key] - baseline[key] for key in current.keys()}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run Orbit eval harness A/B for current vs baseline decay ranker."
    )
    parser.add_argument("--assistant-noise-events", type=int, default=180)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("quality_reports/decay_eval_ab.json"),
    )
    args = parser.parse_args()

    baseline_cls = _load_baseline_ranker_class()

    baseline_report = _run_eval_with_ranker(
        ranker_cls=baseline_cls,
        output_dir=Path("quality_reports/decay_eval_baseline"),
        sqlite_path=Path("tmp/decay_eval_baseline.db"),
        assistant_noise_events=args.assistant_noise_events,
    )

    from decision_engine.retrieval_ranker import RetrievalRanker as current_ranker_cls

    current_report = _run_eval_with_ranker(
        ranker_cls=current_ranker_cls,
        output_dir=Path("quality_reports/decay_eval_current"),
        sqlite_path=Path("tmp/decay_eval_current.db"),
        assistant_noise_events=args.assistant_noise_events,
    )

    baseline_metrics = _metric_slice(baseline_report)
    current_metrics = _metric_slice(current_report)
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "assistant_noise_events": args.assistant_noise_events,
        "baseline": baseline_metrics,
        "current": current_metrics,
        "delta_current_minus_baseline": _delta(current_metrics, baseline_metrics),
        "artifacts": {
            "baseline_json": "quality_reports/decay_eval_baseline/orbit_eval_scorecard.json",
            "current_json": "quality_reports/decay_eval_current/orbit_eval_scorecard.json",
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote eval A/B report to {args.output}")
    print("Delta:", payload["delta_current_minus_baseline"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
