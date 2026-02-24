import { CodeBlock } from "@/components/orbit/code-block"

export default function QuickstartPage() {
  return (
    <div>
      <div className="flex items-center gap-3 mb-6">
        <div className="w-8 h-px bg-primary" />
        <span className="text-primary text-xs tracking-[0.3em] uppercase text-glow-sm">
          Getting Started
        </span>
      </div>
      <h1 className="text-4xl md:text-5xl font-bold text-foreground tracking-tight mb-4">
        Quickstart
      </h1>
      <p className="text-muted-foreground text-base leading-relaxed max-w-xl mb-12">
        Wire Orbit into your app in five steps: install, initialize, ingest, retrieve, feedback.
      </p>

      {/* Step 1 */}
      <div className="mb-12">
        <div className="flex items-center gap-4 mb-4">
          <div className="w-8 h-8 border border-primary flex items-center justify-center text-primary text-sm font-bold">
            1
          </div>
          <h2 className="text-xl font-bold text-foreground">Install the SDK</h2>
        </div>
        <CodeBlock
          code="pip install orbit-memory"
          language="bash"
          filename="terminal"
        />
      </div>

      {/* Step 2 */}
      <div className="mb-12">
        <div className="flex items-center gap-4 mb-4">
          <div className="w-8 h-8 border border-primary flex items-center justify-center text-primary text-sm font-bold">
            2
          </div>
          <h2 className="text-xl font-bold text-foreground">Create a client</h2>
        </div>
        <p className="text-muted-foreground text-sm leading-relaxed mb-4">
          Use a JWT scoped for your Orbit API runtime.
        </p>
        <CodeBlock
          code={`from orbit import MemoryEngine

engine = MemoryEngine(api_key="<jwt-token>")`}
          language="python"
          filename="app.py"
        />
      </div>

      {/* Step 3 */}
      <div className="mb-12">
        <div className="flex items-center gap-4 mb-4">
          <div className="w-8 h-8 border border-primary flex items-center justify-center text-primary text-sm font-bold">
            3
          </div>
          <h2 className="text-xl font-bold text-foreground">Ingest user and assistant signals</h2>
        </div>
        <p className="text-muted-foreground text-sm leading-relaxed mb-4">
          Ingest both sides of the interaction so retrieval can model progress, style, and outcomes.
        </p>
        <CodeBlock
          code={`engine.ingest(
    content="User completed lesson 10",
    event_type="learning_progress",
    entity_id="alice",
)`}
          language="python"
          filename="app.py"
        />
      </div>

      {/* Step 4 */}
      <div className="mb-12">
        <div className="flex items-center gap-4 mb-4">
          <div className="w-8 h-8 border border-primary flex items-center justify-center text-primary text-sm font-bold">
            4
          </div>
          <h2 className="text-xl font-bold text-foreground">Retrieve focused context</h2>
        </div>
        <p className="text-muted-foreground text-sm leading-relaxed mb-4">
          Orbit handles ranking, decay, and personalization inference under the hood.
        </p>
        <CodeBlock
          code={`results = engine.retrieve(
    query="What should I know before I answer?",
    entity_id="alice",
    limit=5,
)`}
          language="python"
          filename="app.py"
        />
      </div>

      {/* Step 5 */}
      <div className="mb-12">
        <div className="flex items-center gap-4 mb-4">
          <div className="w-8 h-8 border border-primary flex items-center justify-center text-primary text-sm font-bold">
            5
          </div>
          <h2 className="text-xl font-bold text-foreground">Send feedback</h2>
        </div>
        <p className="text-muted-foreground text-sm leading-relaxed mb-4">
          Feedback is the learning signal. If you skip this, Orbit cannot tune ranking as effectively.
        </p>
        <CodeBlock
          code={`engine.feedback(
    memory_id=results.memories[0].memory_id,
    helpful=True,
    outcome_value=1.0,
)`}
          language="python"
          filename="app.py"
        />
      </div>

      {/* Personalization callout */}
      <div className="border border-primary/30 bg-primary/5 p-6 mb-12">
        <div className="flex items-center gap-2 mb-3">
          <div className="w-2 h-2 bg-primary" />
          <h3 className="text-sm font-bold text-primary">Automatic personalization, no sidecar service</h3>
        </div>
        <p className="text-sm text-muted-foreground leading-relaxed">
          Orbit can create inferred memories from repeated behavior and feedback trends, for example <code className="text-primary">inferred_learning_pattern</code> and <code className="text-primary">inferred_preference</code>. You keep shipping features; Orbit keeps learning users.
        </p>
      </div>

      {/* Next */}
      <div className="border-t border-border pt-8">
        <p className="text-xs text-muted-foreground tracking-wider uppercase mb-2">Next</p>
        <a href="/docs/integration-guide" className="text-foreground hover:text-primary transition-colors font-bold">
          Integration Guide {"->"}
        </a>
      </div>
    </div>
  )
}
