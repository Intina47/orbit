from __future__ import annotations

import argparse
import contextlib
import io
import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from orbit.eval_harness import run_evaluation


def _default_output_dir() -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    return Path("eval_reports") / f"run_{stamp}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run baseline-vs-Orbit personalization evaluation scorecard.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=_default_output_dir(),
        help="Directory for JSON/Markdown scorecard artifacts.",
    )
    parser.add_argument(
        "--sqlite-path",
        type=Path,
        default=Path("tmp") / "orbit_eval.db",
        help="SQLite database path for the evaluation run.",
    )
    parser.add_argument(
        "--assistant-noise-events",
        type=int,
        default=90,
        help="Number of long assistant noise events in the synthetic dataset.",
    )
    parser.add_argument(
        "--embedding-dim",
        type=int,
        default=64,
        help="Embedding dimension used for the local evaluation engine.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose engine logs during evaluation.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.verbose:
        logging.getLogger().setLevel(logging.WARNING)
    if args.verbose:
        report = run_evaluation(
            output_dir=args.output_dir,
            sqlite_path=args.sqlite_path,
            embedding_dim=args.embedding_dim,
            assistant_noise_events=args.assistant_noise_events,
        )
    else:
        with (
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            report = run_evaluation(
                output_dir=args.output_dir,
                sqlite_path=args.sqlite_path,
                embedding_dim=args.embedding_dim,
                assistant_noise_events=args.assistant_noise_events,
            )
    print(json.dumps(report["metrics"], indent=2, ensure_ascii=True))
    print(json.dumps(report["lift"], indent=2, ensure_ascii=True))
    artifacts = report.get("artifacts", {})
    print(f"json_report={artifacts.get('json_path')}")
    print(f"markdown_report={artifacts.get('markdown_path')}")


if __name__ == "__main__":
    main()
