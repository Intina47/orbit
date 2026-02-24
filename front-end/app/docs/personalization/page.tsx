import { CodeBlock } from "@/components/orbit/code-block"

export default function PersonalizationPage() {
  const envVars = [
    { var: "MDE_ENABLE_ADAPTIVE_PERSONALIZATION", default: "true", purpose: "Enable inferred memory generation" },
    { var: "MDE_PERSONALIZATION_REPEAT_THRESHOLD", default: "3", purpose: "Repeated signals needed for pattern inference" },
    { var: "MDE_PERSONALIZATION_SIMILARITY_THRESHOLD", default: "0.82", purpose: "Semantic similarity threshold" },
    { var: "MDE_PERSONALIZATION_WINDOW_DAYS", default: "30", purpose: "Observation window" },
    { var: "MDE_PERSONALIZATION_MIN_FEEDBACK_EVENTS", default: "4", purpose: "Feedback count for preference inference" },
    { var: "MDE_PERSONALIZATION_PREFERENCE_MARGIN", default: "2.0", purpose: "Confidence margin before writing preference memory" },
  ]

  return (
    <div>
      <div className="flex items-center gap-3 mb-6">
        <div className="w-8 h-px bg-primary" />
        <span className="text-primary text-xs tracking-[0.3em] uppercase text-glow-sm">
          Core Concepts
        </span>
      </div>
      <h1 className="text-4xl md:text-5xl font-bold text-foreground tracking-tight mb-4">
        Adaptive Personalization
      </h1>
      <p className="text-muted-foreground text-base leading-relaxed max-w-xl mb-12">
        Orbit builds user understanding from repeated behavior and feedback outcomes. You get inferred profile memory without adding a second personalization service.
      </p>

      {/* What Orbit infers */}
      <h2 className="text-2xl font-bold text-foreground mb-4">What Orbit infers automatically</h2>
      <div className="grid grid-cols-1 gap-px bg-border mb-12">
        <div className="bg-background p-6">
          <code className="text-primary text-sm font-bold">inferred_preference</code>
          <p className="text-xs text-muted-foreground mt-2 leading-relaxed">
            Derived from feedback trends on assistant style. Example: user performs better with concise, step-based explanations.
          </p>
        </div>
        <div className="bg-background p-6">
          <code className="text-primary text-sm font-bold">inferred_learning_pattern</code>
          <p className="text-xs text-muted-foreground mt-2 leading-relaxed">
            Derived from repeated semantically similar user behavior. Example: user repeatedly struggles with loop boundaries.
          </p>
        </div>
      </div>

      {/* Minimal integration */}
      <h2 className="text-2xl font-bold text-foreground mb-4">Minimal integration (FastAPI chatbot)</h2>
      <CodeBlock
        code={`from orbit import MemoryEngine

orbit = MemoryEngine(api_key="<jwt-token>")

def handle_chat(user_id: str, message: str) -> str:
    # 1) store user input
    orbit.ingest(
        content=message,
        event_type="user_question",
        entity_id=user_id,
    )

    # 2) retrieve personalized context
    context = orbit.retrieve(
        query=f"What should I know about {user_id} for: {message}",
        entity_id=user_id,
        limit=5,
    )

    # 3) call your LLM
    answer = "<llm-response>"

    # 4) store assistant output
    orbit.ingest(
        content=answer,
        event_type="assistant_response",
        entity_id=user_id,
    )
    return answer

def handle_feedback(memory_id: str, helpful: bool) -> None:
    orbit.feedback(
        memory_id=memory_id,
        helpful=helpful,
        outcome_value=1.0 if helpful else -1.0,
    )`}
        language="python"
        filename="personalization_chatbot.py"
      />

      {/* Testing personalization */}
      <h2 className="text-2xl font-bold text-foreground mb-4 mt-12">Quick personalization test</h2>
      <div className="space-y-3 mb-6">
        {[
          "Use the same entity_id and ask related questions 3+ times.",
          "Record helpful and unhelpful outcomes with feedback calls.",
          "Retrieve with the same entity_id and inspect top-k ordering.",
          "Verify inferred memories appear with provenance metadata.",
        ].map((step, i) => (
          <div key={i} className="flex items-start gap-3">
            <span className="text-primary text-sm font-bold mt-0.5">{i + 1}.</span>
            <p className="text-sm text-muted-foreground leading-relaxed">{step}</p>
          </div>
        ))}
      </div>

      <CodeBlock
        code={`results = orbit.retrieve(
    query="What do we know about this learner's weak spots?",
    entity_id="alice",
    limit=10,
)
for memory in results.memories:
    provenance = memory.metadata.get("inference_provenance")
    print(memory.event_type, memory.content, provenance)`}
        language="python"
        filename="test_personalization.py"
      />

      {/* Runtime controls */}
      <h2 className="text-2xl font-bold text-foreground mb-6 mt-12">Runtime controls</h2>
      <div className="border border-border mb-12">
        <div className="grid grid-cols-[1fr_80px_1fr] bg-secondary border-b border-border">
          <div className="px-4 py-3 text-xs font-bold text-muted-foreground tracking-wider uppercase">Variable</div>
          <div className="px-4 py-3 text-xs font-bold text-muted-foreground tracking-wider uppercase border-l border-border">Default</div>
          <div className="px-4 py-3 text-xs font-bold text-muted-foreground tracking-wider uppercase border-l border-border">Purpose</div>
        </div>
        {envVars.map((item) => (
          <div key={item.var} className="grid grid-cols-[1fr_80px_1fr] border-b border-border last:border-b-0">
            <div className="px-4 py-3">
              <code className="text-primary text-xs break-all">{item.var}</code>
            </div>
            <div className="px-4 py-3 text-xs text-foreground border-l border-border">{item.default}</div>
            <div className="px-4 py-3 text-xs text-muted-foreground border-l border-border">{item.purpose}</div>
          </div>
        ))}
      </div>

      {/* Next */}
      <div className="border-t border-border pt-8">
        <p className="text-xs text-muted-foreground tracking-wider uppercase mb-2">Next</p>
        <a href="/docs/api-reference" className="text-foreground hover:text-primary transition-colors font-bold">
          API Reference {"->"}
        </a>
      </div>
    </div>
  )
}
