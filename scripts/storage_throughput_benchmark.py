from __future__ import annotations

import json
import statistics
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

# Ensure the local src directory is on sys.path when the script is executed directly.
ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from memory_engine.engine import DecisionEngine
from memory_engine.models.event import Event


def _build_event(index: int) -> Event:
    return Event(
        entity_id="bench_user",
        event_type="user_question",
        description=f"Benchmark ingest event #{index}",
        metadata={"intent": "user_question"},
    )


def _measure_ingest(engine: DecisionEngine, account_key: str, runs: int) -> list[float]:
    durations: list[float] = []
    for idx in range(runs):
        event = _build_event(idx)
        start = time.perf_counter()
        processed = engine.process_input(event)
        decision = engine.make_storage_decision(processed, account_key=account_key)
        engine.store_memory(processed, decision, account_key=account_key)
        durations.append(time.perf_counter() - start)
    return durations


def _measure_retrieve(engine: DecisionEngine, account_key: str, runs: int) -> list[float]:
    durations: list[float] = []
    for idx in range(runs):
        query = f"Benchmark retrieve {idx}"
        start = time.perf_counter()
        engine.retrieve(query=query, top_k=5, account_key=account_key)
        durations.append(time.perf_counter() - start)
    return durations


def main() -> int:
    runs = 50
    db_dir = Path("tmp")
    db_dir.mkdir(exist_ok=True)
    db_path = db_dir / "storage_throughput.db"
    engine = DecisionEngine(db_path=str(db_path))
    account_key = "storage_bench_account"
    try:
        ingest_times = _measure_ingest(engine, account_key=account_key, runs=runs)
        retrieval_times = _measure_retrieve(engine, account_key=account_key, runs=runs)
    finally:
        engine.close()

    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "ingest": {
            "runs": runs,
            "average_ms": statistics.mean(ingest_times) * 1000,
            "stddev_ms": statistics.pstdev(ingest_times) * 1000,
        },
        "retrieve": {
            "runs": runs,
            "average_ms": statistics.mean(retrieval_times) * 1000,
            "stddev_ms": statistics.pstdev(retrieval_times) * 1000,
        },
    }
    report_dir = Path("quality_reports")
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "storage_throughput.json"
    report_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"Storage throughput benchmark complete. Report: {report_path}")
    print(
        f"  ingest avg {payload['ingest']['average_ms']:.2f} ms; "
        f"retrieve avg {payload['retrieve']['average_ms']:.2f} ms"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
