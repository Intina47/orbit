# Memory Decision Engine - Project Specification v2
**Core Principle: LEARNED, NOT HEURISTIC**  
**Version**: 2.0 (Intelligent-First)  
**Status**: Ready for Implementation  
**Last Updated**: 2026-02-21

---

## CORE MANDATE: NO HEURISTICS, NO RULES

Every decision in this system is either:
1. **Embedding-based** (semantic understanding via vectors)
2. **Learned** (optimized via feedback/outcomes)
3. **LLM-powered** (understanding via language models)

**FORBIDDEN**:
- ❌ Regex for entity extraction
- ❌ Hardcoded rules for decay rates
- ❌ Manual importance weights
- ❌ Heuristic-based filtering
- ❌ If-then logic for decisions
- ❌ Configuration magic numbers (must be learned)

**REQUIRED**:
- ✅ Every component has a learning path
- ✅ Every decision can be explained by embeddings or a learned model
- ✅ System improves immediately from day 1 with feedback
- ✅ No manual tuning, only learned adaptation

---

## 1. EXECUTIVE SUMMARY

The Memory Decision Engine (MDE) is an intelligent decision-making system that determines what to remember, how to forget, and how to retrieve. Unlike traditional memory systems that use rules and heuristics, MDE is powered by learned models and embeddings from inception.

**The Key Difference**:
- Traditional memory: "If event_type == 'user_interaction', apply decay_rate X" (brittle)
- MDE approach: "Understand what this event means semantically. Learn from outcomes which memories matter. Adapt decay rates based on evidence." (intelligent)

**Success Criteria**: System makes provably better retention decisions than heuristic-based alternatives.

---

## 2. TECHNOLOGY STACK (MANDATED)

### Language
**Python 3.11+** (same as before)

### Core Components (CHANGED TO BE INTELLIGENT)

| Component | Technology | Purpose | Why Not Heuristic |
|-----------|-----------|---------|------------------|
| **Semantic Understanding** | OpenAI API (Claude via API or text-embedding-3-small) | Understand event meaning, context, relationships | Embeddings capture semantic nuance rules can't |
| **Entity Understanding** | LLM-based extraction (Claude API) | Extract entities, relationships, meaning | LLM understands context; regex misses 90% of real-world patterns |
| **Importance Modeling** | Neural network (small, trained in-memory) | Learn what makes events important | Learned from feedback, adapts per domain |
| **Decay Learning** | Gradient descent on decay curves | Learn how fast things should fade | Optimized per event type, not hardcoded |
| **Retrieval Ranking** | Learned ranking model (gradient boosting or neural net) | Learn which memories matter most | Optimized on real outcomes, not formulas |
| **Vector Storage** | FAISS | Fast semantic search | Industry standard |
| **Relational DB** | SQLite → PostgreSQL | Structured metadata, feedback tracking | Standard |
| **Learning Framework** | PyTorch (small) or JAX/NumPy | Train importance/decay/ranking models | Modern, flexible, GPU-ready if needed |
| **LLM Interface** | Anthropic SDK (Claude for understanding) | Use Claude for semantic understanding | Better than small models for nuanced decisions |

### Why This Approach

**Traditional approach**: Rules + heuristics
```python
# FORBIDDEN - This is brittle garbage
if event_type == "user_interaction":
    importance = 0.8
elif event_type == "system_log":
    importance = 0.2
# This fails immediately on real data
```

**Intelligent approach**: Learn from data
```python
# REQUIRED - This is what we build
importance = importance_model.predict(
    embedding=event_embedding,  # what is this event semantically?
    context=event_context,      # what's the context?
    history=recent_outcomes     # what have we learned about similar events?
)
# Updates continuously from feedback
```

---

## 3. SYSTEM ARCHITECTURE

### 3.1 Data Flow (Intelligent Version)

```
┌──────────────────────────────┐
│    RAW EVENT STREAM          │
│  (No preprocessing)          │
└────────────┬─────────────────┘
             │
             ▼
┌──────────────────────────────┐
│   SEMANTIC ENCODING LAYER    │
│  • Embed with OpenAI/Claude  │
│  • LLM extracts meaning      │
│  • No rules, pure semantics  │
└────────────┬─────────────────┘
             │
             ▼
┌──────────────────────────────┐
│   LEARNED IMPORTANCE MODEL   │
│  • Neural net trained on:    │
│    - embeddings              │
│    - historical outcomes     │
│    - feedback signals        │
│  • Outputs: should_store()?  │
└────────────┬─────────────────┘
             │
             ▼
┌──────────────────────────────┐
│   STORAGE DECISION LAYER     │
│  • Model confidence > 0.6?   │
│    → Store                   │
│  • Model confidence 0.3-0.6? │
│    → Store (ephemeral)       │
│  • Model confidence < 0.3?   │
│    → Discard                 │
└────────────┬─────────────────┘
             │
             ▼
┌──────────────────────────────┐
│   LEARNED DECAY ENGINE       │
│  • Decay rates learned from: │
│    - memory age              │
│    - retrieval patterns      │
│    - outcome signals         │
│  • Runs continuously         │
└────────────┬─────────────────┘
             │
             ▼
┌──────────────────────────────┐
│   PERSISTENT MEMORY STATE    │
│  • Embeddings                │
│  • Metadata                  │
│  • Outcome history           │
└────────────┬─────────────────┘
             │
             ▼
┌──────────────────────────────┐
│   LEARNED RETRIEVAL RANKER   │
│  • Model learns what matters │
│  • Trained on:               │
│    - relevance judgments     │
│    - outcome signals         │
│    - query patterns          │
└──────────────────────────────┘
```

### 3.2 Core Components (Intelligent First)

#### Component 1: Semantic Encoding & Understanding
**Purpose**: Understand what an event means (not extract with rules)

**Process**:
```python
def encode_event(event: RawEvent) -> EncodedEvent:
    """
    Understand an event semantically using embeddings + LLM
    NO RULES. Pure semantic understanding.
    """
    # 1. Get embedding of full event context
    embedding = get_embedding(event.content)
    
    # 2. Use LLM to extract semantic meaning
    semantic_understanding = llm.extract_meaning(
        event.content,
        context="What is this event fundamentally about? "
                "What entities involved? "
                "What's the semantic intent?"
    )
    
    # 3. Embed the semantic meaning (not just raw text)
    meaning_embedding = get_embedding(semantic_understanding)
    
    # 4. Combine semantic and syntactic understanding
    return EncodedEvent(
        raw_embedding=embedding,              # What does the text say?
        semantic_embedding=meaning_embedding,  # What does it MEAN?
        entities=semantic_understanding.entities,  # From LLM, not regex
        relationships=semantic_understanding.relationships,
        intent=semantic_understanding.intent,
        timestamp=event.timestamp,
        raw_content=event.content
    )
```

**Why Not Heuristics**:
- Regex extracts text patterns, not meaning
- "user_id: 123" vs "the user alice" — regex sees nothing, LLM sees user entity
- Semantic understanding captures domain knowledge

**Code Location**: `src/decision_engine/semantic_encoding.py`

---

#### Component 2: Learned Importance Model
**Purpose**: Learn what events are worth remembering (replaces hardcoded scoring)

**Architecture**:
```python
class ImportanceModel:
    """
    Neural network that learns: given event embedding + context, 
    what's the probability this event should be stored?
    
    Trained on: feedback signals from outcomes
    """
    
    def __init__(self):
        # Small neural net: 384 → 256 → 128 → 1
        self.model = nn.Sequential(
            nn.Linear(384, 256),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(256, 128),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(128, 1),
            nn.Sigmoid()  # Output: 0.0-1.0 importance
        )
        self.optimizer = Adam(self.model.parameters(), lr=1e-3)
    
    def predict(self, event_embedding: np.ndarray) -> float:
        """
        Given event embedding, predict importance (0.0-1.0)
        """
        with torch.no_grad():
            tensor = torch.FloatTensor(event_embedding).unsqueeze(0)
            importance = self.model(tensor).item()
        return importance
    
    def train_on_feedback(self, batch):
        """
        Batch format:
        {
            'embeddings': [...],  # Events we retrieved/discarded
            'outcomes': [...]     # Did they help? (1=helpful, 0=not, -1=harmful)
        }
        
        Learn: events that led to positive outcomes should have high importance
        """
        embeddings = torch.FloatTensor(batch['embeddings'])
        outcomes = torch.FloatTensor(batch['outcomes']).unsqueeze(1)
        
        # Normalize outcomes to 0-1
        targets = (outcomes + 1) / 2  # -1→0, 0→0.5, 1→1.0
        
        # Forward pass
        predictions = self.model(embeddings)
        loss = F.binary_cross_entropy(predictions, targets)
        
        # Backward pass
        self.optimizer.zero_grad()
        loss.backward()
        self.optimizer.step()
        
        return loss.item()
```

**Training Loop**:
- Collect feedback on retrieved/discarded memories
- Train model to predict importance from embeddings
- Model learns what makes events valuable
- No manual tuning of importance weights

**Code Location**: `src/decision_engine/importance_model.py`

---

#### Component 3: Learned Decay Engine
**Purpose**: Learn how fast different events should fade

**Architecture**:
```python
class DecayLearner:
    """
    Learn decay rates per semantic category.
    
    Given: "This event is semantically about user preferences"
    Learn: How fast should user preference memories fade?
    
    Answer: Look at outcome signals for similar events over time
    """
    
    def __init__(self):
        # Track decay effectiveness per semantic cluster
        self.semantic_decay_rates = {}  # semantic_hash → decay_rate
        self.outcome_history = defaultdict(list)
    
    def predict_decay_rate(self, semantic_hash: str, event_age_hours: int) -> float:
        """
        Predict current importance given age and semantic category
        
        learned_decay = learned_rate[semantic_hash]
        current_importance = initial_importance * exp(-learned_decay * hours)
        """
        if semantic_hash not in self.semantic_decay_rates:
            # Default: medium decay, learn from outcomes
            return 0.01
        return self.semantic_decay_rates[semantic_hash]
    
    def learn_from_outcomes(self):
        """
        Observe: for memories of this semantic type,
        which ones aged well (still useful at day 30)?
        which ones became worthless quickly (useless at day 1)?
        
        Adjust decay rate: faster for quick-staling info, slower for persistent
        """
        for semantic_hash, outcomes in self.outcome_history.items():
            # Group outcomes by memory age
            old_outcomes = [o for o in outcomes if o['memory_age_days'] > 14]
            
            if not old_outcomes:
                continue
            
            # How many old memories were useful?
            still_useful_rate = sum(1 for o in old_outcomes if o['was_helpful']) / len(old_outcomes)
            
            current_decay = self.semantic_decay_rates.get(semantic_hash, 0.01)
            
            # If still useful → slow decay. If not useful → fast decay
            if still_useful_rate > 0.6:
                new_decay = current_decay * 0.8  # Slower decay
            elif still_useful_rate < 0.3:
                new_decay = current_decay * 1.2  # Faster decay
            
            self.semantic_decay_rates[semantic_hash] = new_decay
```

**Why Not Heuristics**:
- Hardcoded: "user_preferences fade in 30 days" (wrong for many cases)
- Learned: observes actual outcomes, adapts per semantic category
- Improves over time as system sees more data

**Code Location**: `src/decision_engine/decay_learner.py`

---

#### Component 4: Learned Retrieval Ranker
**Purpose**: Learn which memories matter for retrieval (not formula-based ranking)

**Architecture**:
```python
class RetrievalRanker:
    """
    Learn: given query embedding + retrieved memory embeddings,
    which ranking leads to the best outcomes?
    
    NOT: rank_score = 0.5*similarity + 0.3*recency + 0.2*frequency
    YES: Learn weights from actual outcome signals
    """
    
    def __init__(self):
        # Gradient boosting model or small neural net
        self.ranker_model = GradientBoostingRanker(n_estimators=100)
        self.training_data = []
    
    def feature_vector(self, query_embedding, memory_embedding, memory_metadata):
        """
        Features for ranking model (learned, not manual):
        - Embedding similarity (cosine)
        - Recency (time since memory created)
        - Retrieval frequency (how often retrieved before)
        - Previous outcome signals (was it helpful last time?)
        - Semantic relevance (LLM judgment)
        """
        return np.array([
            cosine_similarity(query_embedding, memory_embedding),
            exp(-0.0001 * memory_metadata['age_hours']),  # Recency signal
            log(memory_metadata['retrieval_count'] + 1),  # Frequency signal
            memory_metadata['avg_outcome_signal'],  # Past helpfulness
            memory_metadata['semantic_relevance'],  # LLM relevance score
        ])
    
    def rank(self, query_embedding: np.ndarray, 
             candidate_memories: List[Memory]) -> List[RankedMemory]:
        """
        Use learned model to rank memories
        """
        if not self.ranker_model.is_trained():
            # Before learning, use basic similarity ranking
            return basic_rank_by_similarity(query_embedding, candidate_memories)
        
        features = np.array([
            self.feature_vector(query_embedding, m.embedding, m.metadata)
            for m in candidate_memories
        ])
        
        scores = self.ranker_model.predict(features)
        ranked = sorted(zip(candidate_memories, scores), key=lambda x: x[1], reverse=True)
        
        return [RankedMemory(m, score) for m, score in ranked]
    
    def learn_from_retrieval_outcome(self, query, ranked_memories, user_feedback):
        """
        User says: "Memory at position 2 was actually what I needed"
        
        Learn: The features of that memory should rank it higher
        """
        for rank_pos, memory in enumerate(ranked_memories):
            # Create training sample
            features = self.feature_vector(query.embedding, memory.embedding, memory.metadata)
            
            # Label: Did user find this helpful at this rank position?
            was_helpful = memory.memory_id in user_feedback['helpful_ids']
            wrong_rank = rank_pos > 0 and was_helpful  # Should be ranked higher
            
            self.training_data.append((features, was_helpful))
        
        # Train in batches (every 100 outcomes)
        if len(self.training_data) >= 100:
            self.ranker_model.fit(
                np.array([x[0] for x in self.training_data]),
                np.array([x[1] for x in self.training_data])
            )
            self.training_data = []
```

**Why Not Heuristics**:
- Hardcoded formula: "rank = 0.5*sim + 0.3*recency + 0.2*freq" (assumes weights)
- Learned: model learns optimal ranking from actual outcomes
- Improves as system sees more queries and feedback

**Code Location**: `src/decision_engine/retrieval_ranker.py`

---

## 4. IMPLEMENTATION ROADMAP

### Week 1: Semantic Encoding + Importance Model
- [ ] Semantic encoding pipeline (embeddings + LLM extraction)
- [ ] Importance neural network architecture
- [ ] Training loop for importance model
- [ ] Unit tests (embeddings, LLM calls, model predictions)
- [ ] **Completion Criteria**: Can encode events semantically, predict importance, train on feedback

### Week 2: Storage + Decay Learning
- [ ] Storage manager (persist encoded events)
- [ ] Decay learner (track decay rates per semantic category)
- [ ] Background decay process
- [ ] Integration tests
- [ ] **Completion Criteria**: Events stored, decay learns from outcomes

### Week 3: Retrieval Ranker + Integration
- [ ] Retrieval ranker (learned ranking model)
- [ ] Feedback collection pipeline
- [ ] Full integration of all components
- [ ] End-to-end tests
- [ ] **Completion Criteria**: Rank-to-outcome feedback loop working

### Week 4: Lab Testing
- [ ] Comprehensive lab tests
- [ ] Performance benchmarks
- [ ] Metrics and observability
- [ ] **Completion Criteria**: All lab tests pass, system is intelligent and adaptive

---

## 5. TESTING STRATEGY

### 5.1 Core Testing Principle

**Traditional**: Test that rules work correctly
```python
# FORBIDDEN
def test_entity_extraction():
    assert regex.findall(r'\d+') == ['123']  # Brittle!
```

**Intelligent**: Test that learning works
```python
# REQUIRED
def test_importance_learning():
    """
    Train importance model on feedback.
    Verify it learns to predict importances.
    """
    # Train on events with known outcomes
    model.train(training_events, outcomes)
    
    # Test on new events
    new_event_embedding = encode("User completed task")
    importance = model.predict(new_event_embedding)
    
    # It should learn: task completion is important
    assert importance > 0.7
```

### 5.2 Critical Lab Tests

**Test 1: Importance Model Learning**

```python
def test_importance_model_learns_from_feedback():
    """
    Train importance model on synthetic feedback.
    Verify it learns to recognize important events.
    """
    # Create 1000 test events with ground truth importance
    test_events = [
        ("User completed critical task", importance=0.9),
        ("System log entry", importance=0.2),
        ("User asked question", importance=0.7),
        # ... 997 more
    ]
    
    # Encode and train
    embeddings = [encode(content) for content, _ in test_events]
    importances = [importance for _, importance in test_events]
    
    model = ImportanceModel()
    for epoch in range(10):
        loss = model.train_on_feedback({
            'embeddings': embeddings,
            'outcomes': [(imp - 0.5) * 2 for imp in importances]  # -1 to 1
        })
        print(f"Epoch {epoch}: Loss {loss:.4f}")
    
    # Test on held-out events
    test_event = encode("User completed final project")
    predicted_importance = model.predict(test_event)
    
    # Model should learn this is important
    assert predicted_importance > 0.75
    
    # Verify it doesn't memorize
    random_event = encode("xyz abc 123")
    predicted_random = model.predict(random_event)
    assert predicted_random < 0.5
```

**Pass Criteria**:
- ✅ Model trains without errors
- ✅ Loss decreases over epochs
- ✅ Predictions are reasonable
- ✅ Model generalizes (doesn't memorize)

---

**Test 2: Decay Learning**

```python
def test_decay_learns_from_outcomes():
    """
    Create synthetic memory lifecycle.
    Verify decay learner adapts rates based on outcomes.
    """
    learner = DecayLearner()
    
    # Simulate memory lifecycle: new → middle-aged → old
    memory_semantic_type = "user_preference"
    
    # Young memories: mostly helpful
    for age in [1, 2, 3]:  # days
        learner.record_outcome(
            semantic_hash=memory_semantic_type,
            age_days=age,
            was_helpful=True
        )
    
    # Old memories: mostly not helpful
    for age in [20, 25, 30]:  # days
        learner.record_outcome(
            semantic_hash=memory_semantic_type,
            age_days=age,
            was_helpful=False
        )
    
    # Learn
    initial_decay = learner.predict_decay_rate(memory_semantic_type, 0)
    learner.learn_from_outcomes()
    new_decay = learner.predict_decay_rate(memory_semantic_type, 0)
    
    # Decay rate should increase (user prefs fade faster than initial guess)
    assert new_decay > initial_decay
```

**Pass Criteria**:
- ✅ Decay rates learned per semantic type
- ✅ Rates adjust based on outcomes
- ✅ No hardcoded values

---

**Test 3: Retrieval Ranker Learning**

```python
def test_retrieval_ranker_learns_from_feedback():
    """
    Create query-memory pairs.
    Provide feedback on ranking quality.
    Verify ranker learns to rank better.
    """
    ranker = RetrievalRanker()
    
    # Create 100 query-memory-feedback triplets
    for i in range(100):
        query = create_test_query()
        candidates = create_test_memories(query, count=10)
        
        # Get initial ranking (before training)
        initial_ranking = ranker.rank(query.embedding, candidates)
        
        # User provides feedback: which memory was actually useful?
        user_feedback = identify_helpful_memory(query, candidates)
        
        # Ranker learns from this feedback
        ranker.learn_from_retrieval_outcome(query, initial_ranking, user_feedback)
    
    # After learning, test on new queries
    test_query = create_test_query()
    test_candidates = create_test_memories(test_query, count=10)
    
    new_ranking = ranker.rank(test_query.embedding, test_candidates)
    
    # Verify learned ranking is better
    # (Memory that was helpful before should rank higher)
    helpful_memory_rank = find_rank(helpful_memory_id, new_ranking)
    assert helpful_memory_rank < 3  # Should be in top 3
```

**Pass Criteria**:
- ✅ Ranker trains without errors
- ✅ Ranking improves with feedback
- ✅ Top-k recall improves over iterations

---

## 6. SUCCESS CRITERIA

### Checkpoint 1: Week 2
- [ ] Semantic encoding works (embeddings + LLM extraction)
- [ ] Importance model trains on feedback and makes predictions
- [ ] Storage persists encoded events
- [ ] Decay learner tracks and learns decay rates
- [ ] Code coverage: 90%+ on critical components

**Gate**: Can encode → score → store → decay (no heuristics)

### Checkpoint 2: Week 3
- [ ] Retrieval ranker learns from feedback
- [ ] End-to-end flow: event → encode → importance → store → decay → retrieve → rank
- [ ] All models training without errors
- [ ] Feedback loop connected

**Gate**: Full intelligent pipeline working

### Checkpoint 3: Week 4
- [ ] All lab tests passing
- [ ] Models learn from feedback (not hardcoded)
- [ ] System improves over time
- [ ] Can articulate why each decision was made (learned, not ruled)
- [ ] Code coverage: 90%+

**Gate**: Lab-standard intelligent brain ready

---

## 7. WHAT SUCCESS LOOKS LIKE

You can say:

> "Our memory system is intelligent from day one. We don't use rules or heuristics. Instead:
>
> - **Semantic Understanding**: Events are understood via embeddings and LLM, not regex
> - **Importance**: A neural network learns what makes events important from feedback
> - **Decay**: Decay rates are learned per semantic category from outcome signals
> - **Retrieval**: A ranking model learns which memories matter for queries
>
> The system improves immediately with feedback. No manual tuning. No hardcoded weights. Just learning."

---

## 8. WHAT NOT TO BUILD

### ❌ DO NOT BUILD
- Entity extraction via regex (use LLM)
- Hardcoded importance scoring (use neural network)
- Manual decay rate configuration (learn from outcomes)
- Formula-based ranking (use learned ranker)
- Heuristic filters (use embedding similarity)

### ✅ DO BUILD
- LLM-powered semantic understanding
- Neural networks trained on feedback
- Learned decay curves per semantic category
- Learned ranking models
- Continuous improvement loops

---

## 9. CODE STRUCTURE

```
memory-decision-engine/
├── src/
│   └── decision_engine/
│       ├── semantic_encoding.py       # LLM + embeddings
│       ├── importance_model.py        # Neural net for importance
│       ├── decay_learner.py           # Learn decay per category
│       ├── retrieval_ranker.py        # Learned ranking
│       ├── storage_manager.py         # Persist + retrieve
│       ├── models.py                  # Data models
│       ├── config.py                  # Configuration
│       └── observability.py           # Logging, metrics
├── tests/
│   ├── unit/
│   ├── integration/
│   └── lab/
├── pyproject.toml
├── pytest.ini
├── mypy.ini
└── ruff.toml
```

---

## 10. FINAL MANDATE

**This is not negotiable**: If you're tempted to use a rule, a hardcoded weight, or a heuristic, STOP. Instead:

1. Ask: "Can this be learned from data?"
2. If yes: Build the learning mechanism
3. If no: Question if you actually need it

Every part of this system should improve with feedback. No manual knobs. No magic numbers. Just intelligence.

Build it right.
