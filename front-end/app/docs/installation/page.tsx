import { CodeBlock } from "@/components/orbit/code-block"

const setupRoutes = [
  {
    title: "Orbit Cloud (Hosted)",
    summary: "Fastest path. Orbit runs the API/runtime. You install the SDK and use your Orbit API key.",
    bestFor: "Teams that want production memory immediately without running infrastructure.",
  },
  {
    title: "Self-Hosted Orbit",
    summary: "You run Orbit API + Postgres + metrics stack yourself via Docker and your own env config.",
    bestFor: "Teams that need local development control, private-network deployment, or custom infra policy.",
  },
]

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
        Installation & Setup Routes
      </h1>
      <p className="text-muted-foreground text-base leading-relaxed max-w-2xl mb-12">
        Orbit supports two clear setup routes: <strong>Cloud</strong> (we host it) and <strong>Self-Hosted</strong> (you run it). Pick one path and follow the exact steps below.
      </p>

      {/* Route chooser */}
      <h2 className="text-2xl font-bold text-foreground mb-4">Choose your route</h2>
      <div className="grid grid-cols-1 gap-px bg-border mb-12">
        {setupRoutes.map((route) => (
          <div key={route.title} className="bg-background p-6">
            <h3 className="text-sm font-bold text-foreground mb-2">{route.title}</h3>
            <p className="text-xs text-muted-foreground leading-relaxed mb-2">{route.summary}</p>
            <p className="text-xs text-muted-foreground leading-relaxed">
              <span className="text-foreground font-semibold">Best for:</span> {route.bestFor}
            </p>
          </div>
        ))}
      </div>

      {/* Common step */}
      <h2 className="text-2xl font-bold text-foreground mb-4">Step 0 (Common): Install SDK</h2>
      <CodeBlock code="pip install orbit-memory" language="bash" filename="terminal" />

      <p className="text-muted-foreground text-sm leading-relaxed mb-6">
        Optional extras for provider adapters:
      </p>
      <div className="grid grid-cols-1 gap-px bg-border mb-12">
        {[
          { group: "pip install orbit-memory[anthropic]", desc: "Anthropic adapter" },
          { group: "pip install orbit-memory[gemini]", desc: "Google Gemini adapter" },
          { group: "pip install orbit-memory[ollama]", desc: "Ollama adapter" },
          { group: "pip install orbit-memory[llm-adapters]", desc: "All adapters" },
        ].map((item) => (
          <div key={item.group} className="bg-background flex items-center justify-between p-4">
            <code className="text-sm text-primary">{item.group}</code>
            <span className="text-xs text-muted-foreground">{item.desc}</span>
          </div>
        ))}
      </div>

      {/* Route A */}
      <h2 className="text-2xl font-bold text-foreground mb-4">Route A: Orbit Cloud (Hosted by Orbit)</h2>

      <h3 className="text-lg font-bold text-foreground mb-3">1) Create/get your Orbit API key</h3>
      <p className="text-muted-foreground text-sm leading-relaxed mb-6">
        From Orbit dashboard (<a href="/dashboard" className="text-primary hover:underline">/dashboard</a>), create a project API key (for example: <code className="text-primary">orbit_pk_...</code>).
      </p>

      <h3 className="text-lg font-bold text-foreground mb-3">2) Add project env</h3>
      <CodeBlock
        code={`ORBIT_API_KEY=orbit_pk_your_key_here
ORBIT_BASE_URL=https://orbit-api-ic4qh4dzga-uc.a.run.app`}
        language="bash"
        filename=".env"
      />

      <h3 className="text-lg font-bold text-foreground mb-3 mt-8">3) Initialize SDK client</h3>
      <CodeBlock
        code={`import os
from orbit import MemoryEngine

engine = MemoryEngine(
    api_key=os.getenv("ORBIT_API_KEY"),
    base_url=os.getenv("ORBIT_BASE_URL", "https://orbit-api-ic4qh4dzga-uc.a.run.app"),
)`}
        language="python"
        filename="app.py"
      />

      <h3 className="text-lg font-bold text-foreground mb-3 mt-8">4) Smoke test ingest + retrieve</h3>
      <CodeBlock
        code={`engine.ingest(
    content="User likes quick vegetarian meals",
    event_type="preference_stated",
    entity_id="demo-user",
)

result = engine.retrieve(
    query="What should I remember for meal planning?",
    entity_id="demo-user",
    limit=5,
)
print(len(result.memories))`}
        language="python"
        filename="smoke_test.py"
      />

      {/* Route B */}
      <h2 className="text-2xl font-bold text-foreground mb-4 mt-12">Route B: Self-Hosted Orbit (Local/Own Infra)</h2>

      <h3 className="text-lg font-bold text-foreground mb-3">1) Clone and start the stack</h3>
      <CodeBlock
        code={`git clone https://github.com/Intina47/orbit.git
cd orbit
docker compose up --build`}
        language="bash"
        filename="terminal"
      />

      <h3 className="text-lg font-bold text-foreground mb-3 mt-8">2) Generate local JWT</h3>
      <CodeBlock
        code={`python scripts/generate_jwt.py \\
  --secret orbit-dev-secret-change-me \\
  --issuer orbit \\
  --audience orbit-api \\
  --subject local-dev`}
        language="bash"
        filename="terminal"
      />

      <h3 className="text-lg font-bold text-foreground mb-3 mt-8">3) Add project env</h3>
      <CodeBlock
        code={`ORBIT_JWT_TOKEN=<paste-generated-token>
ORBIT_API_BASE_URL=http://localhost:8000
ORBIT_JWT_ISSUER=orbit
ORBIT_JWT_AUDIENCE=orbit-api`}
        language="bash"
        filename=".env"
      />

      <h3 className="text-lg font-bold text-foreground mb-3 mt-8">4) Verify Orbit API is healthy</h3>
      <CodeBlock
        code={`curl http://localhost:8000/v1/health
curl http://localhost:8000/v1/metrics`}
        language="bash"
        filename="terminal"
      />

      <h3 className="text-lg font-bold text-foreground mb-3 mt-8">5) Initialize SDK client</h3>
      <CodeBlock
        code={`import os
from orbit import MemoryEngine

engine = MemoryEngine(
    api_key=os.getenv("ORBIT_JWT_TOKEN"),
    base_url=os.getenv("ORBIT_API_BASE_URL", "http://localhost:8000"),
)`}
        language="python"
        filename="app.py"
      />

      {/* Integration modes */}
      <h2 className="text-2xl font-bold text-foreground mb-6 mt-12">Integration modes after setup</h2>
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

      {/* Validation checklist */}
      <h2 className="text-2xl font-bold text-foreground mb-4">Setup validation checklist</h2>
      <div className="space-y-3 mb-12">
        {[
          "SDK installed successfully (pip install orbit-memory).",
          "You can initialize MemoryEngine with your chosen route credentials.",
          "A test ingest call returns stored=True.",
          "A test retrieve call returns memories without auth/network errors.",
          "Feedback endpoint works for at least one memory_id.",
        ].map((item, i) => (
          <div key={i} className="flex items-start gap-3">
            <div className="w-5 h-5 border border-border flex items-center justify-center shrink-0 mt-0.5">
              <span className="text-xs text-muted-foreground">{i + 1}</span>
            </div>
            <p className="text-sm text-muted-foreground leading-relaxed">{item}</p>
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
