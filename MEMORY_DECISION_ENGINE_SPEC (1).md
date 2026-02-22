# Memory Decision Engine - Project Specification
**Version 1.0** | **Status: Ready for Implementation** | **Last Updated: February 2026**

---

## Executive Summary

This document specifies the **Decision Engine Core** — the intelligent decision-making system that determines what gets stored, how it decays, what gets retrieved, and how the system learns from outcomes.

**This is not optional.** This spec is prescriptive. You build exactly what is specified here, test using the exact testing methodology outlined, and declare readiness only when all criteria are met.

**Core Principle:** The Decision Engine is the differentiator. Everything else is infrastructure. Build this right.

---

## 1. ARCHITECTURE SPECIFICATION

### 1.1 System Context

```
┌─────────────────────────────────────────────────────────────┐
│                    Agent Application                         │
│              (External, Not Built Here)                      │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ↓ (Events)
┌─────────────────────────────────────────────────────────────┐
│              DECISION ENGINE (This Spec)                     │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │    Input     │  │   Decision   │  │   Learning   │      │
│  │  Processing  │→→│   Logic      │→→│   Loop       │      │
│  │   (Stage 1)  │  │   (Stage 2)  │  │   (Stage 3)  │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│                                                               │
└──────┬──────────────────────────────────────────────┬────────┘
       │                                              │
       ↓ (Store)                              ↓ (Query)
┌────────────────┐                      ┌────────────────┐
│  Storage Layer │                      │ Retrieval      │
│  (Not Detailed │                      │ Ranking        │
│   in This Spec)│                      │ (Part of DE)   │
└────────────────┘                      └────────────────┘
```

The Decision Engine **owns**:
- What gets stored (filtering & selection)
- How stored items decay over time
- How retrieval ranking works
- How the system learns from agent outcomes

The Decision Engine **does NOT own**:
- Vector encoding (use external embeddings)
- Physical storage (use vector DB + relational DB)
- Agent logic (external responsibility)

### 1.2 Three Processing Stages

#### Stage 1: Input Processing
**Input:** Raw event from agent
**Output:** Processed event with features extracted

Process:
1. Validate event schema
2. Extract semantic content (delegate to embedding API)
3. Extract entity references (rule-based + heuristic)
4. Assign temporal signals (recency)
5. Assign frequency signals (how often seen before)
6. Output: `ProcessedEvent` object

**No machine learning here.** This is deterministic.

#### Stage 2: Decision Logic
**Input:** ProcessedEvent + current memory state
**Output:** Storage decision + metadata

Process:
1. Compute relevance score: `f(recency, frequency, entity_importance)`
2. Apply decay policy: Would this event decay fast or slow?
3. Check compression opportunities: Should this merge with existing memory?
4. Determine graph connections: What entities/memories does this connect to?
5. **Make storage decision:** Store? Store compressed? Skip?
6. Output: `StorageDecision` object

**This is where intelligence lives.** See Section 2 for exact formulas.

#### Stage 3: Learning Loop
**Input:** Retrieval log (what memory was used) + outcome (success/failure)
**Output:** Updated decision weights

Process:
1. Track which memories were retrieved
2. Track agent outcome (success indicator provided by agent)
3. Compare retrieved memory quality vs. outcome
4. Update relevance scoring weights (increase for good outcomes)
5. Update decay curves (slower decay for frequently-useful memories)
6. Output: Updated weights for next cycle

**This runs continuously,** not in batches.

---

## 2. DECISION LOGIC SPECIFICATION

### 2.1 Relevance Score Computation

**Formula:**
```
relevance_score = (α × recency_score) + (β × frequency_score) + (γ × entity_importance_score)
```

Where:
- `α = 0.4` (recency weight)
- `β = 0.3` (frequency weight)
- `γ = 0.3` (entity importance weight)

**Initial values.** You may adjust these after testing, but these are your starting point.

#### Recency Score
```
recency_score = exp(-λ_r × days_since_event)
```

Where:
- `λ_r = 0.1` (decay constant for recency; event half-life ≈ 6.9 days)
- `days_since_event = (now - event_timestamp) / 86400`

**Implementation note:** Use `math.exp()`, not approximate.

#### Frequency Score
```
frequency_score = 1 - exp(-λ_f × times_seen)
```

Where:
- `λ_f = 0.3` (frequency constant)
- `times_seen = count of semantically similar events seen before`

**Semantic similarity detection:** For MVP, consider two events "similar" if they:
- Reference the same entity (user, object, topic)
- Occur within 7 days of each other
- Share >70% token overlap in description

This is a heuristic. It's not perfect. That's okay for MVP.

#### Entity Importance Score
```
entity_importance_score = min(1.0, entity_reference_count / 10)
```

Where:
- `entity_reference_count = total times this entity appears in past events`

**Cap at 1.0.** An entity seen 10+ times gets max score.

### 2.2 Storage Decision Threshold

**Rule:**
```
IF relevance_score >= STORAGE_THRESHOLD:
  STORE the event
ELSE:
  DISCARD the event
```

Where:
- `STORAGE_THRESHOLD = 0.3` (initial value)

**This means:** By default, 30% of events get stored. Adjust threshold to hit target memory efficiency (see Section 4.2).

**No exceptions.** This is deterministic. The only variation is in the weight updates during learning.

### 2.3 Decay Policy Assignment

**Rule:** Each stored event gets assigned a decay half-life based on event type.

**Decay Half-Lives (days):**
- User preference memories: 90 days
- Conversation context: 1 day
- Task execution logs: 7 days
- Learned patterns: 30 days
- Episodic events (facts): 14 days

**Default:** "Episodic events" category (14 days)

**Implementation:** 
```python
decay_half_life = DECAY_POLICY[event_type]
decay_lambda = math.log(2) / decay_half_life
```

**The system will learn to adjust these,** but start with these defaults.

### 2.4 Compression Detection

**Rule:** If 5+ events with same entity and event type exist within 7 days, propose compression.

**Compression format:**
```
Original (5 events):
  - User X bought item A at time T1
  - User X bought item B at time T2
  - User X bought item C at time T3
  - User X bought item A again at time T4
  - User X bought item D at time T5

Compressed (1 memory):
  - User X purchased [item_count: 4, item_types: A, B, C, D]
    within [start_time: T1, end_time: T5]
    entity: User X, category: purchase_history
```

**Store only the compressed version.** Delete originals.

**Cost:** We lose granularity (which specific day X bought A). **Benefit:** 5x storage reduction, faster retrieval.

**This is the tradeoff.** Accept it for MVP.

---

## 3. TECHNOLOGY STACK SPECIFICATION

### 3.1 Languages & Runtimes

**Primary Language:** Python 3.11+
**Why:** Fast iteration, data science libraries, excellent testing frameworks

**Runtime Environment:**
- OS: Linux (Ubuntu 22.04+)
- Python: 3.11 or 3.12
- Package manager: Poetry (mandatory, not pip)

**Why Poetry:** Reproducible builds, deterministic dependencies, lock files

### 3.2 Core Dependencies

```toml
[tool.poetry.dependencies]
python = "^3.11"
numpy = "^1.24"
pandas = "^2.0"
sqlalchemy = "^2.0"
psycopg2-binary = "^2.9"
faiss-cpu = "^1.7.4"
pydantic = "^2.0"
pydantic-settings = "^2.0"
pytest = "^7.0"
pytest-cov = "^4.0"
pytest-benchmark = "^4.0"
python-dotenv = "^1.0"
structlog = "^23.0"
```

**No optional dependencies.** Lock every version. Use `poetry lock` immediately.

### 3.3 External APIs (Required)

**Embedding API:** OpenAI API
- Model: `text-embedding-3-small`
- Why: Fast, cheap, reliable
- Alternative if needed: Use local `nomic-embed-text` (free, open source)
- Cost consideration: Budget ~$50/month for MVP testing

**Do not use:** HuggingFace Transformers (slower, you manage inference)

### 3.4 Storage (Local MVP)

**Vector Storage:** FAISS (Facebook AI Similarity Search)
- Why: Local, no infrastructure, fast indexing, perfect for MVP
- File-based persistence: Store index as `.idx` file
- Configuration: L2 distance metric, 512-dim embeddings

**Relational Storage:** SQLite3 (NOT Postgres for MVP)
- Why: Zero setup, single file, sufficient for testing
- File: `memory.db`
- Later migration to Postgres is trivial

**In-Memory Cache:** Python dict + LRU (functools.lru_cache)
- Why: Fast retrieval ranking without DB hits

### 3.5 Code Organization

**Directory structure (mandatory):**
```
memory-decision-engine/
├── poetry.lock                    (DO NOT EDIT MANUALLY)
├── pyproject.toml                 (Single source of truth for deps)
├── README.md                      (Usage + architecture overview)
├── .env.example                   (Template)
├── .gitignore                     (Python standard)
│
├── src/
│   └── memory_engine/
│       ├── __init__.py
│       ├── config.py              (Settings, pydantic BaseSettings)
│       ├── logger.py              (structlog setup)
│       │
│       ├── models/
│       │   ├── __init__.py
│       │   ├── event.py           (Pydantic model for input event)
│       │   ├── processed_event.py (After Stage 1 processing)
│       │   ├── storage_decision.py (Storage decision + metadata)
│       │   └── memory_state.py    (Current memory snapshot)
│       │
│       ├── stage1_input/
│       │   ├── __init__.py
│       │   ├── processor.py       (InputProcessor class)
│       │   ├── embedding.py       (Call embedding API)
│       │   └── extractors.py      (Entity extraction, heuristics)
│       │
│       ├── stage2_decision/
│       │   ├── __init__.py
│       │   ├── logic.py           (DecisionLogic class)
│       │   ├── scoring.py         (Relevance score computation)
│       │   ├── decay.py           (Decay policy assignment)
│       │   └── compression.py     (Compression detection)
│       │
│       ├── stage3_learning/
│       │   ├── __init__.py
│       │   ├── loop.py            (LearningLoop class)
│       │   ├── feedback.py        (Process feedback from agent)
│       │   └── weight_updater.py  (Update weights/curves)
│       │
│       ├── storage/
│       │   ├── __init__.py
│       │   ├── vector_store.py    (FAISS wrapper)
│       │   ├── db.py              (SQLAlchemy models, SQLite)
│       │   └── retrieval.py       (Query interface, ranking)
│       │
│       └── engine.py              (Main DecisionEngine orchestrator)
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py                (Pytest fixtures)
│   │
│   ├── unit/
│   │   ├── test_stage1.py
│   │   ├── test_stage2_scoring.py
│   │   ├── test_stage2_decay.py
│   │   ├── test_stage2_compression.py
│   │   ├── test_stage3.py
│   │   └── test_storage.py
│   │
│   ├── integration/
│   │   ├── test_end_to_end.py
│   │   ├── test_workflow.py
│   │   └── test_learning_convergence.py
│   │
│   └── benchmarks/
│       ├── test_throughput.py
│       ├── test_latency.py
│       └── test_memory_efficiency.py
│
├── scripts/
│   ├── generate_test_data.py      (Synthetic agent events)
│   ├── run_lab_tests.py           (Test harness)
│   └── dashboard.py               (Simple CLI dashboard)
│
└── docs/
    ├── ARCHITECTURE.md
    ├── FORMULAS.md
    └── TESTING.md

```

**This structure is non-negotiable.** It enforces separation of concerns.

---

## 4. TESTING SPECIFICATION

### 4.1 Testing Principles

1. **Unit tests are mandatory.** Every function has a test.
2. **Integration tests validate workflows.** Stage 1 → Stage 2 → Storage.
3. **Benchmark tests measure efficiency.** Latency, throughput, memory.
4. **Lab tests validate behavior.** Does memory actually work?

### 4.2 Unit Tests

**Coverage Target:** 95%+ line coverage

**Test File:** `tests/unit/test_stage2_scoring.py` (example)

```python
import pytest
from memory_engine.stage2_decision.scoring import compute_relevance_score

class TestRelevanceScoring:
    
    def test_recency_exponential_decay(self):
        """Recency score should decay exponentially with time."""
        score_now = compute_relevance_score(
            recency_days=0, frequency_count=5, entity_ref_count=10
        )
        score_7d = compute_relevance_score(
            recency_days=7, frequency_count=5, entity_ref_count=10
        )
        
        assert score_now > score_7d
        # At 7 days (half-life ~6.9d), should be ~0.5 of original
        assert 0.45 < (score_7d / score_now) < 0.55
    
    def test_frequency_saturation(self):
        """Frequency score should saturate at 1.0."""
        score_1x = compute_relevance_score(
            recency_days=0, frequency_count=1, entity_ref_count=10
        )
        score_20x = compute_relevance_score(
            recency_days=0, frequency_count=20, entity_ref_count=10
        )
        
        assert score_20x < 1.0
        assert score_20x > score_1x
    
    def test_weight_proportions(self):
        """α:β:γ should be 0.4:0.3:0.3."""
        score = compute_relevance_score(
            recency_days=0, frequency_count=5, entity_ref_count=10
        )
        # If recency=1, frequency=1, entity=1, score should be ~0.4+0.3+0.3=1.0
        # (after normalization)
        assert 0.9 < score <= 1.0

    def test_threshold_boundary(self):
        """Events at threshold should be stored; below should not."""
        stored_score = 0.31
        discarded_score = 0.29
        
        assert stored_score >= 0.3
        assert discarded_score < 0.3
```

**Rule:** Every formula has corresponding tests with concrete numbers.

### 4.3 Integration Tests

**File:** `tests/integration/test_end_to_end.py`

```python
import pytest
from memory_engine.engine import DecisionEngine
from memory_engine.models.event import Event

class TestEndToEndWorkflow:
    
    @pytest.fixture
    def engine(self, tmp_path):
        """Create engine with temporary storage."""
        engine = DecisionEngine(db_path=str(tmp_path / "test.db"))
        yield engine
        engine.close()
    
    def test_event_flows_through_all_stages(self, engine):
        """Single event should flow through Stage 1, 2, 3."""
        event = Event(
            timestamp=1000,
            entity_id="user_123",
            event_type="purchase",
            description="User bought a coffee"
        )
        
        # Process event
        processed = engine.process_input(event)
        assert processed.entity_references == ["user_123"]
        assert processed.embedding is not None
        
        # Make decision
        decision = engine.make_storage_decision(processed)
        assert hasattr(decision, 'store')
        assert hasattr(decision, 'decay_half_life')
        
        # Actually store if decision says so
        if decision.store:
            engine.store_memory(processed, decision)
            assert engine.memory_count() > 0
    
    def test_compression_actually_happens(self, engine):
        """5+ similar events should compress into 1."""
        # Add 5 purchase events for same user
        for i in range(5):
            event = Event(
                timestamp=1000 + (i * 3600),
                entity_id="user_123",
                event_type="purchase",
                description=f"User bought item {i}"
            )
            processed = engine.process_input(event)
            decision = engine.make_storage_decision(processed)
            if decision.store:
                engine.store_memory(processed, decision)
        
        # Should have compressed to 1
        assert engine.memory_count() == 1
        memory = engine.get_memory(entity_id="user_123")[0]
        assert memory.is_compressed == True
        assert memory.original_count == 5

    def test_retrieval_ranking_returns_top_k(self, engine):
        """Retrieve should return most relevant memories first."""
        # Add 10 memories with varying relevance
        for i in range(10):
            event = Event(
                timestamp=1000 + (i * 86400),  # Spread over 10 days
                entity_id=f"user_{i}",
                event_type="interaction",
                description="User interacted with system"
            )
            processed = engine.process_input(event)
            decision = engine.make_storage_decision(processed)
            if decision.store:
                engine.store_memory(processed, decision)
        
        # Query for recent events
        results = engine.retrieve(query="recent user", top_k=3)
        assert len(results) <= 3
        # Should be sorted by relevance (most recent first)
        if len(results) >= 2:
            assert results[0].relevance_score >= results[1].relevance_score
```

### 4.4 Benchmark Tests

**File:** `tests/benchmarks/test_throughput.py`

```python
import pytest
from memory_engine.engine import DecisionEngine
from memory_engine.models.event import Event

class TestThroughput:
    
    @pytest.mark.benchmark
    def test_process_1000_events(self, benchmark, engine):
        """Can the engine process 1000 events in reasonable time?"""
        events = [
            Event(
                timestamp=1000 + i,
                entity_id=f"user_{i % 100}",
                event_type="interaction",
                description=f"Event {i}"
            )
            for i in range(1000)
        ]
        
        def process_all():
            for event in events:
                processed = engine.process_input(event)
                decision = engine.make_storage_decision(processed)
                if decision.store:
                    engine.store_memory(processed, decision)
        
        result = benchmark(process_all)
        # Should complete in < 10 seconds
        assert result < 10.0

    @pytest.mark.benchmark
    def test_retrieval_latency(self, benchmark, engine):
        """Retrieval should be <100ms even with 10k memories."""
        # Pre-populate with 10k memories
        for i in range(10000):
            event = Event(
                timestamp=1000 + i,
                entity_id=f"user_{i % 100}",
                event_type="interaction",
                description=f"Memory {i}"
            )
            processed = engine.process_input(event)
            decision = engine.make_storage_decision(processed)
            if decision.store:
                engine.store_memory(processed, decision)
        
        def retrieve():
            return engine.retrieve(query="recent event", top_k=10)
        
        result = benchmark(retrieve)
        assert result < 0.1  # 100ms
```

### 4.5 Lab Tests (Behavioral Validation)

These tests validate that the *brain actually works*, not just that code runs.

**File:** `tests/integration/test_learning_convergence.py`

```python
import pytest
from memory_engine.engine import DecisionEngine
from memory_engine.models.event import Event
import numpy as np

class TestLearningBehavior:
    
    def test_decay_matches_intuition_task_memories(self, engine):
        """Task memories should decay to ~50% relevance in 7 days."""
        event = Event(
            timestamp=0,
            entity_id="task_123",
            event_type="task_execution",
            description="Completed data processing task"
        )
        
        processed = engine.process_input(event)
        decision = engine.make_storage_decision(processed)
        stored_memory = engine.store_memory(processed, decision)
        
        # Immediately after storage
        relevance_now = stored_memory.get_current_relevance()
        
        # Simulate 7 days later
        relevance_7d = stored_memory.get_relevance_at(days_since_storage=7)
        
        # Task memories have 7-day half-life
        # Should decay to ~0.5 of original
        ratio = relevance_7d / relevance_now
        assert 0.45 < ratio < 0.55, f"Expected ~0.5, got {ratio}"
    
    def test_frequently_used_memories_persist_longer(self, engine):
        """
        Memories that help agent succeed should decay slower.
        This validates the learning loop works.
        """
        # Add 20 events of same type
        for i in range(20):
            event = Event(
                timestamp=i * 3600,
                entity_id="user_123",
                event_type="preference_stated",
                description="User stated preference"
            )
            processed = engine.process_input(event)
            decision = engine.make_storage_decision(processed)
            if decision.store:
                stored = engine.store_memory(processed, decision)
                # Simulate: agent used this memory, got success
                engine.record_outcome(
                    memory_id=stored.id,
                    outcome="success"
                )
        
        # Get the compressed memory
        memory = engine.get_memory(entity_id="user_123")[0]
        
        # Check its decay curve was updated (learning loop worked)
        # Should have slower decay than default
        default_half_life = 14  # days
        actual_half_life = memory.decay_half_life_days
        
        # After success signal, should be slower decay
        assert actual_half_life > default_half_life, \
            f"Learning didn't work: {actual_half_life} vs {default_half_life}"

    def test_noise_events_discarded(self, engine):
        """
        Low-relevance events should be discarded.
        High-relevance events should be stored.
        """
        # High-relevance event (recent, frequent entity)
        high_rel_event = Event(
            timestamp=10000,  # Very recent
            entity_id="important_user",  # Seen 50x before
            event_type="preference_stated",
            description="User stated critical preference"
        )
        
        # Low-relevance event (old, rare entity)
        low_rel_event = Event(
            timestamp=1,  # Very old
            entity_id="user_never_seen_before",
            event_type="random_event",
            description="Random one-off thing"
        )
        
        high_decision = engine.make_storage_decision(
            engine.process_input(high_rel_event)
        )
        low_decision = engine.make_storage_decision(
            engine.process_input(low_rel_event)
        )
        
        assert high_decision.store == True, "High-rel should store"
        assert low_decision.store == False, "Low-rel should discard"
    
    def test_compression_preserves_queryability(self, engine):
        """
        After compression, should still be able to query the data.
        """
        # Add 10 events that will compress
        for i in range(10):
            event = Event(
                timestamp=1000 + (i * 1000),
                entity_id="user_123",
                event_type="purchase",
                description=f"Purchased item {i}"
            )
            processed = engine.process_input(event)
            decision = engine.make_storage_decision(processed)
            if decision.store:
                engine.store_memory(processed, decision)
        
        # Query for this user
        results = engine.retrieve(query="user_123 purchase", top_k=5)
        
        # Should get compressed memory back
        assert len(results) > 0
        compressed = results[0]
        assert compressed.is_compressed == True
        # Should have info about purchases
        assert "purchase" in compressed.description.lower() or \
               compressed.original_count == 10
```

### 4.6 Test Execution & Passing Criteria

**Run all tests:**
```bash
pytest tests/ -v --cov=src/memory_engine --cov-report=html
```

**Must pass:**
1. All unit tests (100% for production code paths)
2. All integration tests (no flakiness, repeatable)
3. All benchmarks within thresholds:
   - Throughput: 1000 events in <10 seconds
   - Retrieval latency: <100ms for 10k memories
   - Memory efficiency: >60% compression ratio on repetitive data
4. All lab tests (behavioral validation)

**Coverage requirement:** 95% line coverage minimum.

**Flakiness allowed:** 0%. Every test passes every run.

---

## 5. SUCCESS CRITERIA & READINESS GATES

### 5.1 Correctness Gate

**You pass this gate when:**

1. ✅ All 50+ unit tests pass consistently
2. ✅ Code coverage is 95%+
3. ✅ All formulas match spec exactly (no approximations)
4. ✅ Input/output schemas validated with Pydantic
5. ✅ No panics, all errors handled gracefully

**How to verify:**
```bash
pytest tests/unit/ -v --cov=src/memory_engine
# Must show: 50+ passed, 0 failed, coverage >= 95%
```

### 5.2 Behavior Gate

**You pass this gate when:**

1. ✅ **Decay behavior is correct:**
   - Task memories decay to 50% relevance in 7 days ± 5%
   - User preferences decay to 50% relevance in 90 days ± 5%
   - Conversation context decays to 50% relevance in 1 day ± 5%

2. ✅ **Relevance scoring matches intuition:**
   - Recent events score higher than old events (same other factors)
   - Frequent entities score higher than rare entities
   - Weights sum correctly (α + β + γ ≈ 1.0)

3. ✅ **Storage decisions filter correctly:**
   - 70-80% of events discarded (hitting ~20-30% storage ratio)
   - High-relevance events always stored
   - Low-relevance events always discarded

4. ✅ **Compression works:**
   - 5+ similar events compress to 1 memory
   - Compression ratio ≥ 60% on repetitive data
   - Compressed memories still queryable

5. ✅ **Retrieval ranking works:**
   - Top results are most relevant to query
   - Recent memories rank higher (all else equal)
   - Related entities surface correctly

**How to verify:**
```bash
pytest tests/integration/test_learning_convergence.py -v
# All tests must pass
```

### 5.3 Performance Gate

**You pass this gate when:**

1. ✅ **Throughput:** Process 1000 events in <10 seconds
   - Target: ~100 events/sec
   - Acceptable range: 50-200 events/sec

2. ✅ **Retrieval latency:** Query in <100ms even with 10k memories
   - Target: <50ms
   - Acceptable range: 20-100ms

3. ✅ **Memory efficiency:** Storage is <2x the compressed data size
   - Expected: ~30% of original event stream stored
   - Index overhead acceptable

**How to verify:**
```bash
pytest tests/benchmarks/ -v
# All benchmarks must pass thresholds
```

### 5.4 Code Quality Gate

**You pass this gate when:**

1. ✅ **Linting:** No warnings
   ```bash
   pylint src/memory_engine --fail-under=9.0
   # Score must be >= 9.0/10
   ```

2. ✅ **Type checking:** No unhandled types
   ```bash
   mypy src/memory_engine --strict
   # Must pass with 0 errors
   ```

3. ✅ **Code style:** Follows PEP 8
   ```bash
   black src/ --check
   isort src/ --check
   # Must pass
   ```

4. ✅ **Documentation:**
   - Every public function has docstring
   - Every class has docstring
   - Formulas documented with examples

**How to verify:**
```bash
# Run all checks
make lint
make type-check
make format-check
make test-coverage
```

(You'll create a Makefile with these targets.)

### 5.5 Readiness Checklist

**ONLY declare Phase 1 complete when ALL of these are checked:**

- [ ] All unit tests pass (pytest tests/unit/)
- [ ] All integration tests pass (pytest tests/integration/)
- [ ] All benchmarks pass (pytest tests/benchmarks/)
- [ ] Code coverage >= 95% (pytest --cov)
- [ ] Pylint score >= 9.0
- [ ] Mypy passes (--strict)
- [ ] Black formatting passes
- [ ] All docstrings present
- [ ] README.md complete with usage examples
- [ ] ARCHITECTURE.md explains design decisions
- [ ] FORMULAS.md lists all equations with derivations
- [ ] TESTING.md explains test strategy
- [ ] .env.example created with all required vars
- [ ] poetry.lock committed (no changes to manual deps)
- [ ] Git history clean, meaningful commits
- [ ] No TODOs in code (all resolved)

**You are done with Phase 1 when every box is checked.**

---

## 6. DELIVERABLES FOR PHASE 1

### 6.1 Code Deliverables

1. **Source code** (`src/memory_engine/`)
   - All modules per Section 3.5
   - 95%+ test coverage
   - Passes all linting/type checks

2. **Tests** (`tests/`)
   - Unit, integration, benchmark tests
   - All pass 100% consistently
   - No flaky tests

3. **Configuration**
   - `pyproject.toml` with locked dependencies
   - `poetry.lock` (auto-generated, committed)
   - `.env.example` with all required variables
   - `Makefile` with targets: `lint`, `type-check`, `format-check`, `test`, `test-coverage`

4. **Documentation**
   - `README.md`: Installation, usage, architecture overview
   - `docs/ARCHITECTURE.md`: Design decisions, trade-offs
   - `docs/FORMULAS.md`: All equations with examples
   - `docs/TESTING.md`: Test strategy, running tests
   - Inline docstrings for all public functions/classes

### 6.2 Artifact Deliverables

1. **Lab Test Report**
   - Date, environment (Python version, OS)
   - Test results: all gates passed
   - Metrics table:
     - Decay behavior (actual vs. expected)
     - Relevance scores (sample computations)
     - Storage ratios (% stored vs. discarded)
     - Compression ratios (before/after)
     - Throughput (events/sec)
     - Retrieval latency (ms per query)
     - Memory efficiency (storage size)

2. **Git Repository**
   - Initialized, all code committed
   - Meaningful commit messages
   - README present
   - License (choose: MIT or your preferred)

---

## 7. IMPLEMENTATION WORKFLOW

### Week 1: Setup + Stage 1

**Days 1-2: Project Setup**
- Initialize Poetry project
- Create directory structure
- Write Pydantic models (Event, ProcessedEvent)
- Set up pytest with fixtures
- Create Makefile

**Days 3-5: Stage 1 Input Processing**
- Implement InputProcessor class
- Implement embedding API integration (OpenAI or local)
- Implement entity extraction heuristics
- Write unit tests for each component
- Test with synthetic data

**Deliverable:** InputProcessor works end-to-end, 95%+ test coverage

### Week 2: Stage 2 + Storage

**Days 1-2: Stage 2 Decision Logic**
- Implement scoring.py (all three formulas)
- Implement decay.py (policy assignment)
- Implement compression.py (compression detection)
- Write unit tests for each
- Validate numbers match spec exactly

**Days 3-4: Storage Layer**
- Implement FAISS wrapper (vector_store.py)
- Implement SQLAlchemy models (SQLite)
- Implement retrieval ranking (retrieval.py)
- Write integration tests

**Days 5: Testing & Refinement**
- Run lab tests
- Validate decay curves
- Validate storage thresholds
- Fix any discrepancies from spec

**Deliverable:** Stage 1 + Stage 2 + Storage all working, lab tests pass

### Week 3: Stage 3 + Polish

**Days 1-2: Stage 3 Learning Loop**
- Implement feedback processing
- Implement weight updater
- Implement outcome tracking
- Write integration tests

**Days 3-4: Benchmarking**
- Run throughput benchmarks
- Run latency benchmarks
- Optimize hot paths (if needed)
- Document performance characteristics

**Days 5: Final Polish**
- Code review (self-review)
- Full test run
- Documentation completion
- Readiness checklist verification

**Deliverable:** All code complete, all tests pass, all docs done, ready for review

---

## 8. MONITORING & OBSERVABILITY

### 8.1 Logging

**Use structlog** for all logging. Configure it in `logger.py`.

**Log levels:**
- `DEBUG`: Function entry/exit with parameters
- `INFO`: Event stored, event discarded, decision made
- `WARNING`: Compression triggered, weight updated
- `ERROR`: Validation failure, retrieval failure

**Example:**
```python
import structlog

log = structlog.get_logger()

log.info("event_processed", 
         event_id=event.id, 
         entity_id=event.entity_id,
         relevance_score=0.65)

log.warning("compression_triggered",
            entity_id="user_123",
            original_count=5,
            compressed_to=1)
```

**All logs** must be parseable JSON (for later dashboards).

### 8.2 Metrics to Track

In Stage 3 learning loop, collect these metrics continuously:

1. **Storage metrics**
   - Events received (per day)
   - Events stored (per day)
   - Storage ratio (% stored)

2. **Decay metrics**
   - Average memory age (days)
   - % memories at each age bucket (0-7d, 7-14d, etc.)

3. **Relevance metrics**
   - Average relevance score (stored memories)
   - Relevance score distribution (histogram)

4. **Learning metrics**
   - Weight update frequency
   - Average weight magnitude
   - Convergence rate (is it stabilizing?)

5. **Performance metrics**
   - Event processing latency (p50, p95, p99)
   - Retrieval latency (p50, p95, p99)
   - Storage efficiency (MB per memory)

These get dumped to a `metrics.json` file daily.

---

## 9. COMMON PITFALLS TO AVOID

1. **Don't skip testing.** Write tests as you code, not after.
2. **Don't approximate formulas.** Use exact math.exp(), not lookups.
3. **Don't use vague entity detection.** Document your heuristics precisely.
4. **Don't hardcode thresholds in code.** Use config file.
5. **Don't forget edge cases:** Empty memory state, division by zero, old timestamps.
6. **Don't over-optimize early.** Get correctness first, then performance.
7. **Don't build async without profiling.** Single-threaded is fine for MVP.
8. **Don't commit without linting.** Automate checks in pre-commit hooks.
9. **Don't skip documentation.** Code comments != documentation.
10. **Don't ignore test flakiness.** Every test must be deterministic.

---

## 10. SIGN-OFF CRITERIA

**You are ready to move to Phase 2 (Graph DB + Advanced Learning) only when:**

1. **All tests pass.**
   ```bash
   pytest tests/ -v --cov=src/memory_engine
   # Result: 100+ passed, 0 failed, coverage >= 95%
   ```

2. **All gates passed.** (See Section 5.5 checklist)

3. **Lab tests validate behavior.**
   ```bash
   pytest tests/integration/test_learning_convergence.py -v
   # All behavioral tests pass
   ```

4. **Performance thresholds met.**
   - Throughput: 100+ events/sec
   - Retrieval: <100ms per query
   - Efficiency: >60% compression on repetitive data

5. **Documentation complete.**
   - README, ARCHITECTURE.md, FORMULAS.md, TESTING.md all written

6. **Code quality gates all pass.**
   - Pylint >= 9.0
   - Mypy --strict passes
   - Black formatting passes
   - 95%+ test coverage

**No exceptions.** No moving forward until every criterion is met.

---

## APPENDIX A: Formula Reference

### A.1 Relevance Score
```
relevance_score = 0.4 × recency_score + 0.3 × frequency_score + 0.3 × entity_importance_score

where:
  recency_score = exp(-0.1 × days_since_event)
  frequency_score = 1 - exp(-0.3 × times_seen)
  entity_importance_score = min(1.0, entity_reference_count / 10)
```

### A.2 Decay
```
decay_lambda = ln(2) / decay_half_life

current_relevance = initial_relevance × exp(-decay_lambda × days_elapsed)
```

### A.3 Storage Threshold
```
IF relevance_score >= 0.3:
  STORE
ELSE:
  DISCARD
```

### A.4 Compression Trigger
```
IF count(events with same entity + type within 7 days) >= 5:
  COMPRESS
```

---

## APPENDIX B: Environment Variables

```env
# OpenAI API (if using cloud embeddings)
OPENAI_API_KEY=sk-...
EMBEDDING_MODEL=text-embedding-3-small

# Or local embeddings
USE_LOCAL_EMBEDDINGS=true
LOCAL_EMBEDDING_MODEL=nomic-embed-text

# Storage paths (local MVP)
DB_PATH=./memory.db
VECTOR_DB_PATH=./faiss_index.idx

# Thresholds
STORAGE_THRESHOLD=0.3
COMPRESSION_MIN_COUNT=5
COMPRESSION_TIME_WINDOW_DAYS=7

# Decay half-lives (days)
DECAY_HALFLIFE_PREFERENCE=90
DECAY_HALFLIFE_CONVERSATION=1
DECAY_HALFLIFE_TASK=7
DECAY_HALFLIFE_PATTERN=30
DECAY_HALFLIFE_EPISODIC=14

# Learning
LEARNING_ENABLED=true
WEIGHT_UPDATE_FREQUENCY_HOURS=24

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json
```

---

**Document Version:** 1.0  
**Author:** Memory Infrastructure Team  
**Last Updated:** February 2026  
**Status:** FINAL - Ready for Implementation

This specification is prescriptive and non-negotiable. Build exactly what is specified. Test exactly as specified. Ship when all criteria are met.
