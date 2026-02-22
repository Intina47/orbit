# Architecture

## Overview

The system is implemented in two layers:

1. `src/decision_engine/`
- Intelligent-first core primitives (semantic encoding, learned importance, learned decay, learned ranking, storage manager).

2. `src/memory_engine/`
- v1-compatible stage modules and orchestrator API:
  - Stage 1: input processing (`stage1_input`)
  - Stage 2: decision logic (`stage2_decision`)
  - Stage 3: learning loop (`stage3_learning`)
  - Storage and retrieval (`storage`)

## Data Flow

1. Event ingestion:
- `memory_engine.engine.DecisionEngine.process_input` validates event schema and semantically encodes content.

2. Decisioning:
- `make_storage_decision` uses learned importance score with cold-start prior blend.
- Learned decay rate and half-life metadata are attached.

3. Storage:
- `store_memory` persists to SQLite and vector index abstraction.
- Compression planner collapses repetitive clusters into a compressed memory record.

4. Retrieval:
- Vector preselection via optional FAISS backend or numpy fallback.
- Learned ranker reorders candidates.

5. Learning:
- Outcome feedback updates importance model, ranker, and decay learner continuously.

## Key Design Decisions

1. Learned-first behavior with controlled cold start:
- Decisions are driven by trainable models.
- Deterministic formula prior is retained as a bounded bootstrap signal.

2. Provider abstraction for semantics and embeddings:
- Deterministic providers enable repeatable local tests.
- OpenAI-backed providers are available for production semantics.

3. Compression as explicit storage optimization:
- Repetitive memory clusters are compacted.
- Compression metadata is tracked (`is_compressed`, `original_count`).
