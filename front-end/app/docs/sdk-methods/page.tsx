import { CodeBlock } from "@/components/orbit/code-block"

export default function SdkMethodsPage() {
  return (
    <div>
      <div className="flex items-center gap-3 mb-6">
        <div className="w-8 h-px bg-primary" />
        <span className="text-primary text-xs tracking-[0.3em] uppercase text-glow-sm">API</span>
      </div>
      <h1 className="text-4xl md:text-5xl font-bold text-foreground tracking-tight mb-4">
        SDK Methods
      </h1>
      <p className="text-muted-foreground text-base leading-relaxed max-w-xl mb-12">
        Usage details for <code className="text-primary">MemoryEngine</code> and <code className="text-primary">AsyncMemoryEngine</code>.
      </p>

      {/* ingest */}
      <div className="mb-12">
        <h2 className="text-2xl font-bold text-foreground mb-2">ingest()</h2>
        <p className="text-muted-foreground text-sm leading-relaxed mb-4">
          Store one memory event and return an <code className="text-primary">IngestResponse</code>.
        </p>
        <CodeBlock
          code={`engine.ingest(
    content="I still do not understand Python for loops.",
    event_type="user_question",  # optional but recommended
    metadata={"source": "chat"},  # optional
    entity_id="alice",  # strongly recommended
)`}
          language="python"
          filename="ingest.py"
        />
      </div>

      {/* retrieve */}
      <div className="mb-12">
        <h2 className="text-2xl font-bold text-foreground mb-2">retrieve()</h2>
        <p className="text-muted-foreground text-sm leading-relaxed mb-4">
          Fetch ranked memories for a query. Returns <code className="text-primary">RetrieveResponse</code> with <code className="text-primary">memories</code> list.
        </p>
        <CodeBlock
          code={`results = engine.retrieve(
    query="What should I know about alice?",
    limit=5,  # default: 10
    entity_id="alice",  # optional filter
    event_type="user_question",  # optional filter
    time_range={"start": "2026-01-01", "end": "2026-02-01"},  # optional
)

for memory in results.memories:
    print(memory.content)
    print(memory.metadata.get("inference_provenance"))`}
          language="python"
          filename="retrieve.py"
        />
      </div>

      {/* feedback */}
      <div className="mb-12">
        <h2 className="text-2xl font-bold text-foreground mb-2">feedback()</h2>
        <p className="text-muted-foreground text-sm leading-relaxed mb-4">
          Send outcome signal for a memory ID so Orbit can tune ranking and importance.
        </p>
        <CodeBlock
          code={`engine.feedback(
    memory_id="mem_abc123",
    helpful=True,
    outcome_value=1.0,  # optional, range -1.0 to 1.0
)`}
          language="python"
          filename="feedback.py"
        />
      </div>

      {/* batch */}
      <div className="mb-12">
        <h2 className="text-2xl font-bold text-foreground mb-2">ingest_batch() / feedback_batch()</h2>
        <p className="text-muted-foreground text-sm leading-relaxed mb-4">
          Batch operations for high-throughput pipelines.
        </p>
        <CodeBlock
          code={`# Batch ingest
responses = engine.ingest_batch([
    {"content": "Lesson 1 complete", "event_type": "learning_progress", "entity_id": "alice"},
    {"content": "Lesson 2 complete", "event_type": "learning_progress", "entity_id": "alice"},
])

# Batch feedback
engine.feedback_batch([
    {"memory_id": "mem_abc", "helpful": True, "outcome_value": 1.0},
    {"memory_id": "mem_def", "helpful": False, "outcome_value": -1.0},
])`}
          language="python"
          filename="batch.py"
        />
      </div>

      {/* status */}
      <div className="mb-12">
        <h2 className="text-2xl font-bold text-foreground mb-2">status()</h2>
        <p className="text-muted-foreground text-sm leading-relaxed mb-4">
          Return current usage, quota, and storage stats for the authenticated account.
        </p>
        <CodeBlock
          code={`status = engine.status()
print(status.memory_count, status.storage_used)`}
          language="python"
          filename="status.py"
        />
      </div>

      {/* Async */}
      <div className="border border-primary/30 bg-primary/5 p-6 mb-12">
        <h3 className="text-sm font-bold text-primary mb-2">Async client</h3>
        <p className="text-xs text-muted-foreground leading-relaxed">
          <code className="text-primary">AsyncMemoryEngine</code> mirrors every method above for async frameworks. Same contract, just <code className="text-primary">await</code> and go.
        </p>
      </div>

      <div className="border-t border-border pt-8">
        <p className="text-xs text-muted-foreground tracking-wider uppercase mb-2">Next</p>
        <a href="/docs/rest-endpoints" className="text-foreground hover:text-primary transition-colors font-bold">
          REST Endpoints {"->"}
        </a>
      </div>
    </div>
  )
}
