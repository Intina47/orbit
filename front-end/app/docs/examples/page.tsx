import { CodeBlock } from "@/components/orbit/code-block"

const sdkExamples = [
  {
    name: "basic_usage.py",
    path: "examples/basic_usage.py",
    what: "Smallest possible ingest + retrieve loop using MemoryEngine.",
    run: "python examples/basic_usage.py",
    check: "Confirms SDK wiring and core request flow.",
  },
  {
    name: "async_usage.py",
    path: "examples/async_usage.py",
    what: "Async client usage with AsyncMemoryEngine in event-loop apps.",
    run: "python examples/async_usage.py",
    check: "Confirms async ingest/retrieve works cleanly.",
  },
  {
    name: "batch_operations.py",
    path: "examples/batch_operations.py",
    what: "Batch ingest and batch feedback workflows for higher throughput.",
    run: "python examples/batch_operations.py",
    check: "Confirms ingest_batch + feedback_batch response handling.",
  },
  {
    name: "feedback_loop.py",
    path: "examples/feedback_loop.py",
    what: "Simple positive feedback write after retrieval.",
    run: "python examples/feedback_loop.py",
    check: "Confirms memory_id feedback integration.",
  },
  {
    name: "personalization_quickstart.py",
    path: "examples/personalization_quickstart.py",
    what: "Repeated-signal + feedback flow to trigger inferred memories.",
    run: "python examples/personalization_quickstart.py",
    check: "Confirms inferred pattern/preference memory surfacing.",
  },
]

const liveExamples = [
  {
    name: "live_meal_coach_ollama",
    path: "examples/live_meal_coach_ollama/",
    what: "Consumer-facing product simulation with two modes: baseline vs orbit memory.",
    run: "python -m uvicorn examples.live_meal_coach_ollama.app:app --reload --port 8020",
    check: "Compare response quality and context preview between baseline/orbit modes.",
  },
  {
    name: "live_chatbot_ollama",
    path: "examples/live_chatbot_ollama/",
    what: "Coding tutor with retrieval inspector and memory feedback in browser UI.",
    run: "python -m uvicorn examples.live_chatbot_ollama.app:app --reload --port 8010",
    check: "Verify retrieval ordering and feedback loop from the UI.",
  },
]

const integrationExamples = [
  {
    name: "agent_integration.py",
    path: "examples/agent_integration.py",
    what: "FastAPI chatbot pattern with Orbit + OpenAI call flow.",
    run: "python examples/agent_integration.py",
    check: "Use as implementation template (requires provider credentials).",
  },
]

export default function ExamplesPage() {
  return (
    <div>
      <div className="flex items-center gap-3 mb-6">
        <div className="w-8 h-px bg-primary" />
        <span className="text-primary text-xs tracking-[0.3em] uppercase text-glow-sm">Guides</span>
      </div>
      <h1 className="text-4xl md:text-5xl font-bold text-foreground tracking-tight mb-4">
        Examples
      </h1>
      <p className="text-muted-foreground text-base leading-relaxed max-w-2xl mb-12">
        Real runnable examples from this repo. Start with a live app if you want product behavior fast, then use script-level examples for focused SDK verification.
      </p>

      <h2 className="text-2xl font-bold text-foreground mb-4">Prerequisites for live examples</h2>
      <CodeBlock
        code={`# Orbit API stack up
# (from repo root)
docker compose up --build

# Ollama running locally
# and a root .env file with:
ORBIT_JWT_TOKEN=<your-jwt>
ORBIT_API_BASE_URL=http://localhost:8000
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama3.1`}
        language="bash"
        filename="terminal"
      />

      <h2 className="text-2xl font-bold text-foreground mb-4 mt-12">Live Product Simulations</h2>
      <div className="grid grid-cols-1 gap-px bg-border mb-12">
        {liveExamples.map((example) => (
          <div key={example.path} className="bg-background p-6">
            <div className="flex items-start justify-between gap-4 mb-3">
              <code className="text-sm text-primary font-bold">{example.name}</code>
              <code className="text-xs text-muted-foreground shrink-0">{example.path}</code>
            </div>
            <p className="text-sm text-muted-foreground leading-relaxed mb-3">{example.what}</p>
            <div className="mb-3">
              <p className="text-xs text-muted-foreground mb-1">Run</p>
              <code className="text-xs text-primary">{example.run}</code>
            </div>
            <p className="text-xs text-muted-foreground">
              <span className="text-foreground font-semibold">Verify:</span> {example.check}
            </p>
          </div>
        ))}
      </div>

      <h2 className="text-2xl font-bold text-foreground mb-4">Core SDK Scripts</h2>
      <div className="grid grid-cols-1 gap-px bg-border mb-12">
        {sdkExamples.map((example) => (
          <div key={example.path} className="bg-background p-6">
            <div className="flex items-start justify-between gap-4 mb-3">
              <code className="text-sm text-primary font-bold">{example.name}</code>
              <code className="text-xs text-muted-foreground shrink-0">{example.path}</code>
            </div>
            <p className="text-sm text-muted-foreground leading-relaxed mb-3">{example.what}</p>
            <div className="mb-3">
              <p className="text-xs text-muted-foreground mb-1">Run</p>
              <code className="text-xs text-primary">{example.run}</code>
            </div>
            <p className="text-xs text-muted-foreground">
              <span className="text-foreground font-semibold">Verify:</span> {example.check}
            </p>
          </div>
        ))}
      </div>

      <h2 className="text-2xl font-bold text-foreground mb-4">Integration Templates</h2>
      <div className="grid grid-cols-1 gap-px bg-border mb-12">
        {integrationExamples.map((example) => (
          <div key={example.path} className="bg-background p-6">
            <div className="flex items-start justify-between gap-4 mb-3">
              <code className="text-sm text-primary font-bold">{example.name}</code>
              <code className="text-xs text-muted-foreground shrink-0">{example.path}</code>
            </div>
            <p className="text-sm text-muted-foreground leading-relaxed mb-3">{example.what}</p>
            <div className="mb-3">
              <p className="text-xs text-muted-foreground mb-1">Run</p>
              <code className="text-xs text-primary">{example.run}</code>
            </div>
            <p className="text-xs text-muted-foreground">
              <span className="text-foreground font-semibold">Verify:</span> {example.check}
            </p>
          </div>
        ))}
      </div>

      <div className="border border-primary/30 bg-primary/5 p-6 mt-12">
        <h3 className="text-sm font-bold text-primary mb-2">Recommended evaluation order</h3>
        <div className="space-y-2">
          {[
            "Run live_meal_coach_ollama first to feel consumer-facing personalization (baseline vs orbit).",
            "Run live_chatbot_ollama to inspect retrieval ordering and memory feedback behavior.",
            "Run personalization_quickstart.py to verify inferred-memory generation from repeated signals.",
            "Run batch_operations.py when validating throughput-oriented integration paths.",
          ].map((item, i) => (
            <div key={i} className="flex items-start gap-2">
              <span className="text-primary text-xs mt-0.5">{">"}</span>
              <p className="text-xs text-muted-foreground leading-relaxed">{item}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="border-t border-border pt-8 mt-12">
        <p className="text-xs text-muted-foreground tracking-wider uppercase mb-2">Next</p>
        <a href="/docs/deployment" className="text-foreground hover:text-primary transition-colors font-bold">
          Deployment {"->"}
        </a>
      </div>
    </div>
  )
}
