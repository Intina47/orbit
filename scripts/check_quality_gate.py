from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from orbit.eval_harness import run_evaluation
from orbit.soak_harness import GateThresholds, run_soak_campaign


@dataclass(frozen=True)
class GateCheck:
    name: str
    passed: bool
    value: float
    comparator: str
    threshold: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Orbit quality gates and fail on metric regressions.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("quality_reports") / "latest",
        help="Directory for quality-gate artifacts.",
    )
    parser.add_argument(
        "--sqlite-dir",
        type=Path,
        default=Path("tmp") / "quality_gate",
        help="Directory for SQLite state used by the harnesses.",
    )
    parser.add_argument(
        "--assistant-noise-events",
        type=int,
        default=90,
        help="Assistant-noise events for run_evaluation.",
    )
    parser.add_argument(
        "--soak-turns",
        type=int,
        default=80,
        help="Turns per persona for quick soak gate.",
    )
    parser.add_argument(
        "--soak-probe-interval",
        type=int,
        default=20,
        help="Probe interval for quick soak gate.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=17,
        help="Random seed for soak run.",
    )
    return parser.parse_args()


def main() -> None:
    os.environ.setdefault("LOG_LEVEL", "WARNING")
    args = parse_args()
    output_dir: Path = args.output_dir
    sqlite_dir: Path = args.sqlite_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    sqlite_dir.mkdir(parents=True, exist_ok=True)

    eval_report = run_evaluation(
        output_dir=output_dir / "eval",
        sqlite_path=sqlite_dir / "eval.db",
        assistant_noise_events=args.assistant_noise_events,
    )
    eval_metrics = dict(eval_report["metrics"]["orbit"])

    soak_thresholds = GateThresholds(
        min_precision_at_5=0.30,
        min_top1_relevant_rate=0.60,
        max_stale_memory_rate=0.08,
        max_assistant_noise_rate=0.25,
        min_provenance_type_coverage=0.90,
        min_provenance_derived_coverage=0.70,
    )
    soak_report = run_soak_campaign(
        output_dir=output_dir / "soak",
        sqlite_path=sqlite_dir / "soak.db",
        turns_per_persona=args.soak_turns,
        probe_interval=args.soak_probe_interval,
        seed=args.seed,
        thresholds=soak_thresholds,
    )
    soak_metrics = dict(soak_report["metrics"])
    soak_gates = list(soak_report["gates"])

    checks = [
        _gte("eval_precision_at_5", eval_metrics["avg_precision_at_5"], 0.35),
        _gte("eval_top1_relevant_rate", eval_metrics["top1_relevant_rate"], 0.70),
        _lte("eval_assistant_noise_rate", eval_metrics["assistant_noise_rate"], 0.20),
        _lte("eval_stale_memory_rate", eval_metrics["stale_memory_rate"], 0.08),
        _gte(
            "eval_predicted_helpfulness_rate",
            eval_metrics["predicted_helpfulness_rate"],
            0.70,
        ),
        _gte(
            "soak_inferred_returned_count",
            float(soak_metrics.get("inferred_returned_count", 0.0)),
            1.0,
        ),
    ]
    checks.extend(
        GateCheck(
            name=f"soak_gate_{str(gate.get('name'))}",
            comparator=str(gate.get("comparator")),
            threshold=float(gate.get("threshold", 0.0)),
            value=float(gate.get("value", 0.0)),
            passed=bool(gate.get("passed", False)),
        )
        for gate in soak_gates
    )

    overall_pass = all(item.passed for item in checks)
    summary = {
        "overall_pass": overall_pass,
        "checks": [
            {
                "name": item.name,
                "passed": item.passed,
                "value": round(item.value, 4),
                "comparator": item.comparator,
                "threshold": round(item.threshold, 4),
            }
            for item in checks
        ],
        "eval_metrics": eval_metrics,
        "soak_metrics": soak_metrics,
        "artifacts": {
            "eval_json": eval_report.get("artifacts", {}).get("json_path"),
            "soak_json": soak_report.get("artifacts", {}).get("json_path"),
        },
    }
    summary_path = output_dir / "quality_gate_summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, ensure_ascii=True))
    print(f"summary_path={summary_path}")
    if not overall_pass:
        raise SystemExit(1)


def _gte(name: str, value: float, threshold: float) -> GateCheck:
    return GateCheck(
        name=name,
        value=value,
        comparator=">=",
        threshold=threshold,
        passed=value >= threshold,
    )


def _lte(name: str, value: float, threshold: float) -> GateCheck:
    return GateCheck(
        name=name,
        value=value,
        comparator="<=",
        threshold=threshold,
        passed=value <= threshold,
    )


if __name__ == "__main__":
    main()
