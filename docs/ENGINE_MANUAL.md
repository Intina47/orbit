# Orbit Engine Manual

This is the single internal system manual for the Orbit engine.
When architecture or runtime behavior changes, update this file in the same PR.

## Purpose

Orbit's engine converts raw application events into compact, high-signal memory that can be retrieved with low latency and high personalization quality.

Core contract:
- `ingest`: accept signals and persist/update memory
- `retrieve`: return ranked, relevant context
- `feedback`: learn from outcomes

## Runtime Architecture

### High-level components

1. `InputProcessor` (`stage1_input`)
- Cleans input and creates semantic/raw embeddings.

2. `DecisionLogic` (`stage2_decision`)
- Scores the event, assigns decay policy, and decides tier/store behavior.

3. Storage (`SQLiteStorageManager` or `SQLAlchemyStorageManager`)
- Durable memory persistence and indexed candidate search.

4. `RetrievalRanker` + retrieval service
- Candidate ranking, intent-aware reweighting, diversity controls.

5. `AdaptivePersonalizationEngine`
- Inferred memory generation from repeated patterns/feedback.

6. `LearningLoop`
- Feedback-driven updates to ranking/importance/decay learners.

## Ingest Path

Ingest is write-oriented and should stay lightweight from the caller perspective.

Flow:
1. Event -> processed representation.
2. Decision -> store/discard and tier choice.
3. Core memory write.
4. Flash pipeline maintenance (sync or async mode).

## Flash Pipeline (Ingest-side maintenance)

Goal: keep database memory clean/compact without blocking ingest-critical work.

Tasks:
- conflict/lifecycle checks
- inferred pattern generation
- cluster compaction
- periodic maintenance hooks (decay/recalibration cadence)

### Modes

- `sync` (default): maintenance executes inline.
- `async`: maintenance runs in background queue workers.

Config:
- `MDE_FLASH_PIPELINE_MODE=sync|async`
- `MDE_FLASH_PIPELINE_WORKERS`
- `MDE_FLASH_PIPELINE_QUEUE_SIZE`
- `MDE_FLASH_PIPELINE_MAINTENANCE_INTERVAL`

Operational counters are exposed via `/v1/metrics`.

## Retrieve Path

Retrieve is latency-sensitive and the primary runtime bottleneck.

Current strategy:
1. Semantic candidate preselection.
2. Learned ranking.
3. Query-aware reweighting and diversity handling.
4. Intent caps and inferred-memory probe coverage.
5. Ranked memory response with provenance metadata.

## Data Quality Principles

1. Favor compact, reusable facts over long prompt blobs.
2. Preserve provenance (`why/when/type/derived_from`) for debuggability.
3. Detect and track contested facts instead of silently overwriting.
4. Keep noisy assistant-heavy memories from crowding concise user profile signals.

## Observability

API metrics:
- request totals and latencies
- auth/key-rotation failure counts
- HTTP status totals
- flash pipeline counters/gauges

Flash metrics include:
- mode (`async` vs `sync`)
- worker count
- queue depth/capacity
- enqueued/dropped/runs/failures
- maintenance cycles

## Optimization Notes

1. Ingest optimization:
- Use compact writes and async maintenance where possible.
- Keep expensive lifecycle/compaction/inference off critical path in async mode.

2. Retrieve optimization:
- Optimize candidate pool quality before heavy ranking.
- Preserve top-k precision with diversity constraints and intent caps.

3. Storage optimization:
- Use PostgreSQL in production.
- Keep compaction and inferred-memory lifecycle active to bound growth.

## Known Risks / Follow-ups

1. Truncation risk:
- Compaction can remove useful tail context if not preserved as structured facts/provenance.
- Track with the TODO item for truncation-safe ingest compaction.

2. Async queue pressure:
- In async mode, full queue can drop maintenance tasks (`orbit_flash_pipeline_dropped_total`).
- Monitor queue depth and drops.

## Change Management Rules

When modifying engine behavior:
1. Update this manual in the same PR.
2. Add/adjust tests for changed paths.
3. Expose new operational state in metrics if it affects runtime reliability.
