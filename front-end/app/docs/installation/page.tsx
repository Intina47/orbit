import { CodeBlock } from "@/components/orbit/code-block"

export default function InstallationPage() {
  return (
    <div>
      <div className="flex items-center gap-3 mb-6">
        <div className="w-8 h-px bg-primary" />
        <span className="text-primary text-xs tracking-[0.3em] uppercase text-glow-sm">
          Getting Started
        </span>
      </div>
      <h1 className="text-4xl md:text-5xl font-bold text-foreground tracking-tight mb-4">
        Installation
      </h1>
      <p className="text-muted-foreground text-base leading-relaxed max-w-xl mb-12">
        Install the SDK, pick provider adapters if needed, then run Orbit locally or against your hosted API.
      </p>

      {/* SDK */}
      <h2 className="text-2xl font-bold text-foreground mb-4">Python SDK</h2>
      <CodeBlock code="pip install orbit-memory" language="bash" filename="terminal" />

      <p className="text-muted-foreground text-sm leading-relaxed mb-8">
        Optional extras for LLM adapters:
      </p>

      <div className="grid grid-cols-1 gap-px bg-border mb-12">
        {[
          { group: "pip install orbit-memory[anthropic]", desc: "Anthropic adapter" },
          { group: "pip install orbit-memory[gemini]", desc: "Google Gemini adapter" },
          { group: "pip install orbit-memory[ollama]", desc: "Ollama local adapter" },
          { group: "pip install orbit-memory[llm-adapters]", desc: "All adapters" },
        ].map((item) => (
          <div key={item.group} className="bg-background flex items-center justify-between p-4">
            <code className="text-sm text-primary">{item.group}</code>
            <span className="text-xs text-muted-foreground">{item.desc}</span>
          </div>
        ))}
      </div>

      {/* Local runtime */}
      <h2 className="text-2xl font-bold text-foreground mb-4">Local runtime (Docker)</h2>
      <p className="text-muted-foreground text-sm leading-relaxed mb-4">
        Compose boots Orbit API, PostgreSQL, Prometheus, and OpenTelemetry collector.
      </p>
      <CodeBlock code="docker compose up --build" language="bash" filename="terminal" />

      <h3 className="text-lg font-bold text-foreground mb-3 mt-8">Generate a JWT for local testing</h3>
      <CodeBlock
        code={`python scripts/generate_jwt.py \\
  --secret orbit-dev-secret-change-me \\
  --issuer orbit \\
  --audience orbit-api \\
  --subject local-dev`}
        language="bash"
        filename="terminal"
      />

      <h3 className="text-lg font-bold text-foreground mb-3 mt-8">Run migrations</h3>
      <CodeBlock code="python -m alembic upgrade head" language="bash" filename="terminal" />

      {/* Integration modes */}
      <h2 className="text-2xl font-bold text-foreground mb-6 mt-12">Integration modes</h2>
      <div className="grid grid-cols-1 gap-px bg-border mb-12">
        {[
          { mode: "Python SDK", when: "Python app, fastest integration", entry: "from orbit import MemoryEngine" },
          { mode: "REST API", when: "Polyglot services or gateway architecture", entry: "POST /v1/ingest, GET /v1/retrieve, POST /v1/feedback" },
          { mode: "OpenClaw Plugin", when: "OpenClaw agent runtime with plugin slots", entry: "integrations/openclaw-memory/" },
        ].map((item) => (
          <div key={item.mode} className="bg-background p-6">
            <h3 className="text-sm font-bold text-foreground mb-1">{item.mode}</h3>
            <p className="text-xs text-muted-foreground mb-3">{item.when}</p>
            <code className="text-xs text-primary">{item.entry}</code>
          </div>
        ))}
      </div>

      {/* Next */}
      <div className="border-t border-border pt-8">
        <p className="text-xs text-muted-foreground tracking-wider uppercase mb-2">Next</p>
        <a href="/docs/quickstart" className="text-foreground hover:text-primary transition-colors font-bold">
          Quickstart {"->"}
        </a>
      </div>
    </div>
  )
}
