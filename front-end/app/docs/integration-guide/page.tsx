import { CodeBlock } from "@/components/orbit/code-block"

export default function IntegrationGuidePage() {
  return (
    <div>
      <div className="flex items-center gap-3 mb-6">
        <div className="w-8 h-px bg-primary" />
        <span className="text-primary text-xs tracking-[0.3em] uppercase text-glow-sm">
          Core Concepts
        </span>
      </div>
      <h1 className="text-4xl md:text-5xl font-bold text-foreground tracking-tight mb-4">
        Integration Guide
      </h1>
      <p className="text-muted-foreground text-base leading-relaxed max-w-xl mb-12">
        The practical Orbit contract for production apps. Keep this loop tight and your memory quality will climb instead of drift.
      </p>
      <div className="border border-primary/30 bg-primary/5 p-6 mb-12">
        <h3 className="text-sm font-bold text-primary mb-2">Credential note</h3>
        <p className="text-xs text-muted-foreground leading-relaxed">
          If you run Orbit Cloud, create an API key in <a href="/dashboard" className="text-primary hover:underline">Dashboard</a> and pass it as <code className="text-primary">api_key</code>. For self-hosted, use JWT.
        </p>
      </div>

      {/* Core contract */}
      <h2 className="text-2xl font-bold text-foreground mb-4">Core integration contract</h2>
      <p className="text-muted-foreground text-sm leading-relaxed mb-6">
        Every successful Orbit integration does these three things:
      </p>

      <div className="grid grid-cols-1 gap-px bg-border mb-12">
        <div className="bg-background p-6">
          <div className="flex items-center gap-3 mb-2">
            <span className="text-primary font-bold text-sm">01</span>
            <h3 className="text-sm font-bold text-foreground">Ingest both sides of the conversation</h3>
          </div>
          <p className="text-xs text-muted-foreground leading-relaxed">
            Send user events and assistant responses. A memory engine with one eye closed is still half blind.
          </p>
        </div>
        <div className="bg-background p-6">
          <div className="flex items-center gap-3 mb-2">
            <span className="text-primary font-bold text-sm">02</span>
            <h3 className="text-sm font-bold text-foreground">Use a stable entity_id</h3>
          </div>
          <p className="text-xs text-muted-foreground leading-relaxed">
            Keep <code className="text-primary">entity_id</code> consistent per user or owner scope across ingest and retrieve.
          </p>
        </div>
        <div className="bg-background p-6">
          <div className="flex items-center gap-3 mb-2">
            <span className="text-primary font-bold text-sm">03</span>
            <h3 className="text-sm font-bold text-foreground">Send feedback continuously</h3>
          </div>
          <p className="text-xs text-muted-foreground leading-relaxed">
            Retrieval quality improves when Orbit receives positive and negative outcomes, not just events.
          </p>
        </div>
      </div>

      {/* 5-minute integration */}
      <h2 className="text-2xl font-bold text-foreground mb-4">Minimal SDK flow</h2>
      <CodeBlock
        code={`from orbit import MemoryEngine

engine = MemoryEngine(api_key="<jwt-token>", base_url="http://localhost:8000")

# 1) store user signal
engine.ingest(
    content="I still do not understand Python for loops.",
    event_type="user_question",
    entity_id="alice",
)

# 2) retrieve context
results = engine.retrieve(
    query="What should I know about alice before answering?",
    entity_id="alice",
    limit=5,
)

# 3) store outcome signal
if results.memories:
    engine.feedback(
        memory_id=results.memories[0].memory_id,
        helpful=True,
        outcome_value=1.0,
    )`}
        language="python"
        filename="integration.py"
      />

      {/* Retrieval quality */}
      <h2 className="text-2xl font-bold text-foreground mb-4 mt-12">Retrieval quality guidelines</h2>
      <div className="space-y-4 mb-12">
        {[
          "Filter by entity_id whenever personalization matters.",
          "Start with limit=5 and only increase when you have evidence.",
          "Ingest assistant responses, not only user prompts.",
          "Keep event types semantically consistent across services.",
          "Use feedback for both good and bad outcomes.",
          "When metadata.inference_provenance.clarification_required is true, ask a clarification question before using that memory in safety-sensitive responses.",
          "Inspect inference provenance metadata during QA and incident review.",
        ].map((tip, i) => (
          <div key={i} className="flex items-start gap-3">
            <span className="text-primary text-sm mt-0.5">{">"}</span>
            <p className="text-sm text-muted-foreground leading-relaxed">{tip}</p>
          </div>
        ))}
      </div>

      {/* Next */}
      <div className="border-t border-border pt-8">
        <p className="text-xs text-muted-foreground tracking-wider uppercase mb-2">Next</p>
        <a href="/docs/event-taxonomy" className="text-foreground hover:text-primary transition-colors font-bold">
          Event Taxonomy {"->"}
        </a>
      </div>
    </div>
  )
}
