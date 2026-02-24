from __future__ import annotations

import argparse
import contextlib
import json
import logging
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from orbit.soak_harness import run_soak_campaign


def _default_output_dir() -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    return Path("soak_reports") / f"run_{stamp}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run long-horizon Orbit personalization soak with hard quality gates.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=_default_output_dir(),
        help="Directory for JSON/Markdown soak artifacts.",
    )
    parser.add_argument(
        "--sqlite-path",
        type=Path,
        default=Path("tmp") / "orbit_soak.db",
        help="SQLite database path for soak campaign state.",
    )
    parser.add_argument(
        "--turns-per-persona",
        type=int,
        default=500,
        help="Turns per persona track (recommended 500-1000).",
    )
    parser.add_argument(
        "--probe-interval",
        type=int,
        default=50,
        help="Run probe queries every N turns per persona.",
    )
    parser.add_argument(
        "--embedding-dim",
        type=int,
        default=64,
        help="Embedding dimension used in soak campaign runtime.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=17,
        help="Deterministic random seed for workload generation.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logs during soak run.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not 500 <= args.turns_per_persona <= 1000:
        msg = "--turns-per-persona must be between 500 and 1000."
        raise SystemExit(msg)
    if not args.verbose:
        logging.getLogger().setLevel(logging.WARNING)

    if args.verbose:
        report = run_soak_campaign(
            output_dir=args.output_dir,
            sqlite_path=args.sqlite_path,
            turns_per_persona=args.turns_per_persona,
            probe_interval=args.probe_interval,
            embedding_dim=args.embedding_dim,
            seed=args.seed,
        )
    else:
        with (
            open(os.devnull, "w", encoding="utf-8") as devnull,
            contextlib.redirect_stdout(devnull),
            contextlib.redirect_stderr(devnull),
        ):
            report = run_soak_campaign(
                output_dir=args.output_dir,
                sqlite_path=args.sqlite_path,
                turns_per_persona=args.turns_per_persona,
                probe_interval=args.probe_interval,
                embedding_dim=args.embedding_dim,
                seed=args.seed,
            )

    print(json.dumps(report["metrics"], indent=2, ensure_ascii=True))
    print(json.dumps(report["gates"], indent=2, ensure_ascii=True))
    print(f"overall_pass={report.get('overall_pass')}")
    artifacts = report.get("artifacts", {})
    print(f"json_report={artifacts.get('json_path')}")
    print(f"markdown_report={artifacts.get('markdown_path')}")


if __name__ == "__main__":
    main()
