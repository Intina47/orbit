# Orbit SDK & API Specification
**Version**: 1.0  
**Status**: Ready for Implementation  
**Last Updated**: 2026-02-21

---

## CORE MANDATE

**Developers should integrate Orbit in under 5 minutes.**

Not 5 hours. Not 5 days. Five minutes from `pip install` to first memory ingest.

This means:
- Minimal configuration
- Sensible defaults
- Clear error messages
- Excellent documentation
- Examples that work out-of-the-box

---

## 1. TECHNOLOGY STACK (MANDATED)

### Python SDK
- **Language**: Python 3.11+
- **HTTP Client**: `httpx` (async-first, modern)
- **Type Hints**: Full, mandatory, mypy strict
- **Validation**: Pydantic v2
- **Async**: Built-in, not bolted-on
- **Testing**: pytest + pytest-asyncio
- **Documentation**: Sphinx + ReadTheDocs

### REST API
- **Framework**: FastAPI (async, auto-docs, validation)
- **Server**: Uvicorn (production-ready)
- **Auth**: Bearer tokens (JWT, simple for now)
- **Rate Limiting**: Built-in via slowapi
- **Logging**: Structured (JSON output)
- **Validation**: Pydantic models

### Deployment
- **Docker**: Single container, simple deployment
- **Configuration**: Environment variables (12-factor)
- **Database**: PostgreSQL (upgrade from SQLite)
- **Monitoring**: Prometheus metrics + OpenTelemetry ready

---

## 2. PYTHON SDK SPECIFICATION

### 2.1 Core Architecture

```
┌─────────────────────────────────────────┐
│  MemoryEngine (Main Interface)          │
├─────────────────────────────────────────┤
│  Methods:                               │
│  • ingest(event)                       │
│  • retrieve(query, limit, filters)     │
│  • feedback(memory_id, outcome)        │
│  • status()                            │
│                                         │
│  Config:                                │
│  • api_key                              │
│  • base_url                             │
│  • timeout                              │
│  • max_retries                          │
└─────────────────────────────────────────┘
```

### 2.2 Installation & Setup

**Installation**:
```bash
pip install orbit-memory
```

**Quick Start** (5 minutes):
```python
from orbit import MemoryEngine

# 1. Initialize (one line)
engine = MemoryEngine(api_key="orbit_pk_...")

# 2. Ingest an event (one line)
engine.ingest({
    "content": "User completed task X",
    "event_type": "agent_decision"
})

# 3. Retrieve memories (one line)
results = engine.retrieve("What did the user do?")

# Done.
```

**That's it.** Everything else is optional.

### 2.3 Core Methods

#### Method 1: `ingest(event)`

**Purpose**: Send an event to Orbit. The engine decides what to remember.

**Signature**:
```python
def ingest(
    self,
    content: str,
    event_type: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    entity_id: Optional[str] = None,
) -> IngestResponse:
    """
    Ingest an event into Orbit's memory system.
    
    Args:
        content: The event content (plain text, required)
        event_type: Type of event. Optional, auto-detected if not provided.
                   Examples: "agent_decision", "user_interaction", "system_event"
        metadata: Arbitrary metadata dict. Optional.
                 Examples: {"model": "gpt-4", "temperature": 0.7}
        entity_id: ID of the entity (user, agent, etc). Optional.
                  Examples: "user_alice", "agent_bot_v1"
    
    Returns:
        IngestResponse:
            - memory_id: Unique ID for this memory
            - stored: Boolean, was it stored?
            - importance_score: 0.0-1.0, why did we store/discard?
            - encoded_at: Timestamp when encoded
            - decision_reason: Human-readable why we stored/discarded
    
    Raises:
        OrbitAuthError: Invalid API key
        OrbitValidationError: Missing/invalid content
        OrbitRateLimitError: Rate limit exceeded
        OrbitServerError: Server error (retries automatically)
    
    Example:
        response = engine.ingest(
            content="Agent selected strategy A based on market conditions",
            event_type="agent_decision",
            metadata={"strategy": "A", "confidence": 0.92},
            entity_id="agent_bot_v1"
        )
        
        if response.stored:
            print(f"Memory saved: {response.memory_id}")
            print(f"Importance: {response.importance_score:.2f}")
        else:
            print(f"Not stored: {response.decision_reason}")
    """
```

**Behavior**:
- Semantic encoding happens server-side
- Importance model decides storage
- Returns immediately (set and forget)
- Automatic retry on network failure (3 retries, exponential backoff)
- Detailed logging (can be silenced via config)

**Response Example**:
```python
IngestResponse(
    memory_id="mem_550e8400e29b41d4a716446655440000",
    stored=True,
    importance_score=0.87,
    decision_reason="High semantic relevance to agent behavior patterns",
    encoded_at=datetime(2026, 2, 21, 14, 30, 0),
    latency_ms=45
)
```

---

#### Method 2: `retrieve(query, limit, filters)`

**Purpose**: Query memories and get ranked results.

**Signature**:
```python
def retrieve(
    self,
    query: str,
    limit: int = 10,
    entity_id: Optional[str] = None,
    event_type: Optional[str] = None,
    time_range: Optional[TimeRange] = None,
) -> RetrieveResponse:
    """
    Retrieve ranked memories matching a query.
    
    Args:
        query: Natural language query. Examples:
               "What strategies did the agent try?"
               "What were the user's preferences?"
               "What happened on March 15?"
        limit: Number of results (1-100, default 10)
        entity_id: Filter by entity (optional)
        event_type: Filter by event type (optional)
        time_range: Filter by time (optional)
                   TimeRange(start=datetime(...), end=datetime(...))
    
    Returns:
        RetrieveResponse:
            - memories: List[Memory] - ranked results
            - total_candidates: int - how many matched before ranking
            - query_execution_time_ms: float
            - applied_filters: dict - what filters were used
    
    Each Memory contains:
        - memory_id: str
        - content: str
        - rank_score: float (0.0-1.0)
        - rank_position: int (1 = most relevant)
        - importance_score: float
        - timestamp: datetime
        - metadata: dict
        - relevance_explanation: str (why it ranked here)
    
    Raises:
        OrbitAuthError: Invalid API key
        OrbitValidationError: Invalid query
        OrbitServerError: Server error
    
    Example:
        results = engine.retrieve(
            query="What did the agent learn from failures?",
            limit=5,
            entity_id="agent_bot_v1"
        )
        
        for memory in results.memories:
            print(f"{memory.rank_position}. {memory.content}")
            print(f"   Relevance: {memory.rank_score:.2%}")
            print(f"   Why: {memory.relevance_explanation}")
    """
```

**Behavior**:
- Query is embedded server-side
- Returns top-k ranked by learned ranker
- Includes explanation for each rank
- Fast (< 100ms p99)
- Filters applied before ranking

**Response Example**:
```python
RetrieveResponse(
    memories=[
        Memory(
            memory_id="mem_001",
            content="Agent tried strategy B but it failed due to market volatility",
            rank_position=1,
            rank_score=0.94,
            importance_score=0.87,
            timestamp=datetime(2026, 2, 19, 10, 0),
            relevance_explanation="Direct match on 'agent learned from failure'; high semantic similarity",
            metadata={"strategy": "B", "outcome": "failed"}
        ),
        Memory(
            memory_id="mem_002",
            content="Previous market conditions caused agent to recalibrate risk parameters",
            rank_position=2,
            rank_score=0.78,
            importance_score=0.72,
            timestamp=datetime(2026, 2, 18, 15, 30),
            relevance_explanation="Related to agent learning; mentioned calibration",
            metadata={"adjustment": "risk_params"}
        ),
        # ... more results
    ],
    total_candidates=47,
    query_execution_time_ms=28.5,
    applied_filters={"entity_id": "agent_bot_v1"}
)
```

---

#### Method 3: `feedback(memory_id, helpful, outcome_value)`

**Purpose**: Tell Orbit whether a retrieved memory was useful. System learns from this.

**Signature**:
```python
def feedback(
    self,
    memory_id: str,
    helpful: bool,
    outcome_value: Optional[float] = None,
) -> FeedbackResponse:
    """
    Provide feedback on a retrieved memory.
    Orbit's learning loop uses this to improve ranking and decay.
    
    Args:
        memory_id: ID of the memory you're rating
        helpful: Boolean - was this memory useful?
        outcome_value: Fine-grained signal (-1.0 to 1.0)
                      -1.0: Harmful, wrong, misleading
                       0.0: Neutral, not helpful but not harmful
                       1.0: Very helpful, exactly what was needed
    
    Returns:
        FeedbackResponse:
            - recorded: Boolean - was feedback accepted?
            - memory_id: str
            - learning_impact: str (how this feedback helps)
            - updated_at: datetime
    
    Raises:
        OrbitAuthError: Invalid API key
        OrbitValidationError: Invalid memory_id
        OrbitServerError: Server error
    
    Example:
        # After retrieving and using a memory
        results = engine.retrieve("What happened last time?")
        best_result = results.memories[0]
        
        # Tell Orbit if it was useful
        engine.feedback(
            memory_id=best_result.memory_id,
            helpful=True,
            outcome_value=0.9  # Very helpful
        )
        
        # This improves Orbit's learning:
        # - Ranking model learns this memory ranked correctly
        # - Decay model learns to keep it longer
        # - Importance model learns similar events matter
    """
```

**Behavior**:
- Non-blocking (fire and forget)
- Aggregated by learning loop (every 100 feedback events or daily)
- Updates decay curves, ranking weights, importance model
- No immediate impact (system learns gradually)

**Response Example**:
```python
FeedbackResponse(
    recorded=True,
    memory_id="mem_001",
    learning_impact="Positive signal recorded. This will improve ranking for similar queries.",
    updated_at=datetime(2026, 2, 21, 14, 35)
)
```

---

#### Method 4: `status()`

**Purpose**: Check connection and basic stats.

**Signature**:
```python
def status(self) -> StatusResponse:
    """
    Get system status and usage stats.
    
    Returns:
        StatusResponse:
            - connected: Boolean - can reach Orbit servers?
            - api_version: str - version you're talking to
            - account_usage: dict
                - events_ingested_this_month: int
                - queries_this_month: int
                - storage_usage_mb: float
                - quota: dict
            - latest_ingestion: datetime - when was last event ingested?
            - uptime_percent: float - 99.x% uptime
    
    Example:
        status = engine.status()
        print(f"Connected: {status.connected}")
        print(f"Events this month: {status.account_usage['events_ingested_this_month']}")
        print(f"Storage: {status.account_usage['storage_usage_mb']:.1f} MB")
    """
```

---

### 2.4 Advanced API (Optional, for Power Users)

#### Async Support
```python
from orbit import AsyncMemoryEngine

async def main():
    engine = AsyncMemoryEngine(api_key="orbit_pk_...")
    
    # Non-blocking ingest
    response = await engine.ingest(content="Event 1")
    
    # Parallel requests
    results = await asyncio.gather(
        engine.retrieve("Query 1"),
        engine.retrieve("Query 2"),
        engine.retrieve("Query 3")
    )
```

#### Batch Operations
```python
# Ingest multiple events at once
responses = engine.ingest_batch([
    {"content": "Event 1"},
    {"content": "Event 2"},
    {"content": "Event 3"}
])

# Batch feedback
engine.feedback_batch([
    {"memory_id": "mem_1", "helpful": True},
    {"memory_id": "mem_2", "helpful": False}
])
```

#### Custom Configuration
```python
from orbit import MemoryEngine, Config

engine = MemoryEngine(
    api_key="orbit_pk_...",
    config=Config(
        base_url="https://api.orbit.dev",
        timeout_seconds=30,
        max_retries=3,
        retry_backoff_factor=2.0,
        log_level="debug",  # verbose logging
        enable_telemetry=True  # help us improve
    )
)
```

---

### 2.5 Error Handling

**Custom Exceptions** (inherit from `OrbitError`):
```python
from orbit.exceptions import (
    OrbitError,           # Base exception
    OrbitAuthError,       # 401 - invalid API key
    OrbitValidationError, # 400 - bad request
    OrbitRateLimitError,  # 429 - too many requests
    OrbitNotFoundError,   # 404 - resource not found
    OrbitServerError,     # 500+ - server error (auto-retry)
    OrbitTimeoutError,    # Timeout
)

try:
    results = engine.retrieve("query")
except OrbitAuthError:
    print("Invalid API key. Check your credentials.")
except OrbitRateLimitError:
    print("Rate limited. Wait before retrying.")
except OrbitServerError as e:
    print(f"Server error (retried 3 times): {e}")
```

---

### 2.6 Configuration & Defaults

**Default Config**:
```python
Config(
    api_key=None,  # Required, set via env var ORBIT_API_KEY
    base_url="https://api.orbit.dev",
    timeout_seconds=30,
    max_retries=3,
    retry_backoff_factor=2.0,
    log_level="info",
    user_agent="orbit-python/1.0.0",
    enable_telemetry=True,  # Anonymous usage stats (can disable)
)
```

**Environment Variables** (12-factor):
```bash
ORBIT_API_KEY=orbit_pk_...
ORBIT_BASE_URL=https://api.orbit.dev
ORBIT_TIMEOUT=30
ORBIT_LOG_LEVEL=info
```

---

### 2.7 SDK Project Structure

```
orbit-python/
├── orbit/
│   ├── __init__.py                    # Main exports
│   ├── client.py                      # MemoryEngine class
│   ├── async_client.py                # AsyncMemoryEngine class
│   ├── models.py                      # Pydantic models
│   ├── config.py                      # Configuration
│   ├── exceptions.py                  # Custom exceptions
│   ├── http.py                        # HTTP client wrapper
│   ├── telemetry.py                   # Anonymous usage stats
│   └── logger.py                      # Structured logging
├── tests/
│   ├── unit/
│   │   ├── test_client.py
│   │   ├── test_models.py
│   │   └── test_exceptions.py
│   ├── integration/
│   │   ├── test_api_integration.py
│   │   └── test_real_workflows.py
│   └── fixtures/
│       └── conftest.py
├── examples/
│   ├── basic_usage.py
│   ├── async_usage.py
│   ├── batch_operations.py
│   ├── agent_integration.py           # LangChain example
│   └── feedback_loop.py
├── docs/
│   ├── index.md
│   ├── quickstart.md
│   ├── api_reference.md
│   ├── examples.md
│   └── troubleshooting.md
├── pyproject.toml
├── pytest.ini
├── mypy.ini
├── ruff.toml
└── README.md
```

---

## 3. REST API SPECIFICATION

### 3.1 Endpoints Overview

```
POST   /v1/ingest              - Ingest event
GET    /v1/retrieve            - Retrieve memories
POST   /v1/feedback            - Provide feedback
POST   /v1/ingest/batch        - Batch ingest
POST   /v1/feedback/batch      - Batch feedback
GET    /v1/status              - System status
GET    /v1/health              - Health check
GET    /v1/metrics             - Prometheus metrics
POST   /v1/auth/validate       - Validate token
```

### 3.2 Core Endpoints

#### POST /v1/ingest

**Request**:
```json
{
  "content": "Agent selected strategy A",
  "event_type": "agent_decision",
  "metadata": {
    "model": "gpt-4",
    "temperature": 0.7
  },
  "entity_id": "agent_bot_v1"
}
```

**Response** (201 Created):
```json
{
  "memory_id": "mem_550e8400e29b41d4a716446655440000",
  "stored": true,
  "importance_score": 0.87,
  "decision_reason": "High semantic relevance to agent patterns",
  "encoded_at": "2026-02-21T14:30:00Z",
  "latency_ms": 45
}
```

**Errors**:
- 400 Bad Request: Missing/invalid content
- 401 Unauthorized: Invalid API key
- 429 Too Many Requests: Rate limit
- 500 Server Error: Internal error (retry)

---

#### GET /v1/retrieve

**Query Parameters**:
```
query=string (required)
limit=integer (1-100, default 10)
entity_id=string (optional)
event_type=string (optional)
start_time=ISO8601 (optional)
end_time=ISO8601 (optional)
```

**Example Request**:
```
GET /v1/retrieve?query=What%20did%20the%20agent%20learn?&limit=5&entity_id=agent_bot_v1
```

**Response** (200 OK):
```json
{
  "memories": [
    {
      "memory_id": "mem_001",
      "content": "Agent learned strategy B failed",
      "rank_position": 1,
      "rank_score": 0.94,
      "importance_score": 0.87,
      "timestamp": "2026-02-19T10:00:00Z",
      "relevance_explanation": "Direct semantic match on 'learning'; high similarity",
      "metadata": {"strategy": "B"}
    }
  ],
  "total_candidates": 47,
  "query_execution_time_ms": 28.5,
  "applied_filters": {"entity_id": "agent_bot_v1"}
}
```

---

#### POST /v1/feedback

**Request**:
```json
{
  "memory_id": "mem_001",
  "helpful": true,
  "outcome_value": 0.9
}
```

**Response** (200 OK):
```json
{
  "recorded": true,
  "memory_id": "mem_001",
  "learning_impact": "Positive signal recorded",
  "updated_at": "2026-02-21T14:35:00Z"
}
```

---

### 3.3 Authentication

**Bearer Token** (in Authorization header):
```
Authorization: Bearer orbit_pk_abc123def456
```

**Token Format**:
- Prefix: `orbit_pk_` (public key, safe to share)
- Length: 32 characters
- Issued via dashboard
- Revocable
- Can have scopes (read, write, feedback)

---

### 3.4 Rate Limiting

**Headers** (in response):
```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 987
X-RateLimit-Reset: 1708451700
```

**Limits** (per API key):
- Free tier: 100 events/day, 500 queries/day
- Pro tier: 100K events/day, 100K queries/day
- Enterprise: Custom

**Retry Strategy**:
- 429 response includes `Retry-After` header
- SDK automatically retries with exponential backoff

---

### 3.5 Pagination

For batch responses, use cursor-based pagination:

```
GET /v1/memories?limit=100&cursor=abc123

Response:
{
  "data": [...],
  "cursor": "def456",
  "has_more": true
}
```

---

## 4. IMPLEMENTATION ROADMAP

### Week 1: SDK Core + Testing
- [ ] MemoryEngine class (ingest, retrieve, feedback, status)
- [ ] Model definitions (Pydantic)
- [ ] HTTP client wrapper
- [ ] Exception hierarchy
- [ ] Unit tests (95%+ coverage)
- [ ] **Completion Criteria**: Core SDK works, can ingest/retrieve/feedback locally

### Week 2: API Server + Integration
- [ ] FastAPI application
- [ ] All endpoints implemented
- [ ] Authentication (Bearer tokens)
- [ ] Rate limiting
- [ ] Integration with Decision Engine
- [ ] Integration tests
- [ ] **Completion Criteria**: SDK connects to API, end-to-end flow works

### Week 3: Async, Advanced Features, Examples
- [ ] AsyncMemoryEngine
- [ ] Batch operations
- [ ] Custom configuration
- [ ] Example applications (basic, async, agent integration)
- [ ] **Completion Criteria**: Power users have tools, examples show best practices

### Week 4: Documentation + Polish
- [ ] API documentation (auto-generated from FastAPI)
- [ ] SDK documentation (ReadTheDocs)
- [ ] Troubleshooting guide
- [ ] Migration guide (from other systems)
- [ ] Performance benchmarks
- [ ] **Completion Criteria**: Developer can integrate in < 5 minutes with docs

---

## 5. TESTING STRATEGY

### 5.1 Unit Tests (SDK)

**Test: Basic Ingest**
```python
def test_ingest_stores_event(mock_api):
    engine = MemoryEngine(api_key="test_key")
    
    response = engine.ingest(content="Test event")
    
    assert response.stored == True
    assert response.importance_score >= 0.0
    assert response.memory_id is not None
```

**Test: Retrieve Returns Ranked Results**
```python
def test_retrieve_returns_ranked_results(mock_api):
    engine = MemoryEngine(api_key="test_key")
    
    results = engine.retrieve("What happened?")
    
    assert len(results.memories) > 0
    # Verify ranking order
    for i in range(len(results.memories) - 1):
        assert results.memories[i].rank_score >= results.memories[i+1].rank_score
```

**Test: Error Handling**
```python
def test_invalid_api_key_raises_auth_error(mock_api):
    engine = MemoryEngine(api_key="invalid_key")
    
    with pytest.raises(OrbitAuthError):
        engine.ingest(content="Test")
```

### 5.2 Integration Tests

**Test: End-to-End Flow**
```python
def test_end_to_end_ingest_retrieve_feedback(api_server):
    engine = MemoryEngine(api_key="test_key", base_url=api_server.url)
    
    # 1. Ingest
    response = engine.ingest(
        content="Agent learned strategy A works",
        event_type="agent_decision"
    )
    memory_id = response.memory_id
    
    # 2. Retrieve
    results = engine.retrieve("What strategies work?")
    assert any(m.memory_id == memory_id for m in results.memories)
    
    # 3. Feedback
    feedback_response = engine.feedback(
        memory_id=memory_id,
        helpful=True
    )
    assert feedback_response.recorded == True
```

**Test: Async Operations**
```python
@pytest.mark.asyncio
async def test_async_ingest_and_retrieve(api_server):
    engine = AsyncMemoryEngine(api_key="test_key", base_url=api_server.url)
    
    # Parallel operations
    ingest_task = engine.ingest(content="Event 1")
    retrieve_task = engine.retrieve("Query")
    
    responses = await asyncio.gather(ingest_task, retrieve_task)
    
    assert responses[0].stored == True
    assert len(responses[1].memories) > 0
```

---

## 6. SUCCESS CRITERIA

### Checkpoint 1: SDK Works (End Week 1)
- [ ] Can ingest events
- [ ] Can retrieve memories
- [ ] Can provide feedback
- [ ] All unit tests passing
- [ ] 95%+ code coverage
- [ ] No external dependencies beyond httpx + pydantic

**Gate**: SDK is usable, just not publicly released

### Checkpoint 2: API Works (End Week 2)
- [ ] All endpoints functional
- [ ] Authentication working
- [ ] Rate limiting working
- [ ] Integration tests passing
- [ ] API documentation auto-generated
- [ ] SDK <--> API integration proven

**Gate**: Full end-to-end flow works

### Checkpoint 3: Ready for Release (End Week 4)
- [ ] Documentation complete and clear
- [ ] Examples work out-of-the-box
- [ ] Performance benchmarks meet targets:
  - Ingest: < 50ms average
  - Retrieve: < 100ms p99
  - Feedback: < 20ms
- [ ] Error messages are helpful
- [ ] Async support proven
- [ ] Code coverage: 90%+

**Gate**: Ready to release to early access program

---

## 7. PERFORMANCE TARGETS

### Latency (p99)
- Ingest: < 50ms
- Retrieve: < 100ms
- Feedback: < 20ms
- Status: < 30ms

### Throughput
- Ingest: 1000+ events/second per server
- Retrieve: 100+ queries/second per server

### Reliability
- 99.9% uptime
- Automatic retries on transient failures
- Zero data loss

---

## 8. DEVELOPER EXPERIENCE CHECKLIST

### Installation
- [ ] `pip install orbit-memory` works
- [ ] No build steps required
- [ ] Works on Python 3.11+
- [ ] Works on Windows, Mac, Linux

### Getting Started
- [ ] Can ingest event in < 5 minutes
- [ ] Minimal config required
- [ ] Sensible defaults for everything
- [ ] Clear error messages if something breaks

### Documentation
- [ ] API reference is auto-generated and complete
- [ ] Quickstart guide works end-to-end
- [ ] Examples are practical and copy-paste-able
- [ ] Troubleshooting covers common issues
- [ ] Migration guide from other solutions

### Support
- [ ] GitHub issues are triaged within 24 hours
- [ ] Discord channel for questions
- [ ] Email support for critical issues
- [ ] Status page for uptime

---

## 9. WHAT SUCCESS LOOKS LIKE

A developer can:

1. **Install**: `pip install orbit-memory` (20 seconds)
2. **Configure**: `engine = MemoryEngine(api_key="...")` (30 seconds)
3. **Integrate**: 5 lines of code in their agent (2 minutes)
4. **Use**: Memories automatically being stored and retrieved (immediately)
5. **Improve**: System learns from feedback and improves over time (continuous)

**Total time to first integration**: < 5 minutes

**Sentiment**: "That was easier than I expected."

---

## 10. FINAL MANDATE

**Make integration a joy, not a chore.**

Every line of code you add should either:
1. Make something faster
2. Make something clearer
3. Make something more powerful

If it doesn't do one of those three, don't add it.

Simplicity is the feature.

