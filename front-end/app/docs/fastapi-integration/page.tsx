import { CodeBlock } from "@/components/orbit/code-block"

export default function FastApiIntegrationPage() {
  return (
    <div>
      <div className="flex items-center gap-3 mb-6">
        <div className="w-8 h-px bg-primary" />
        <span className="text-primary text-xs tracking-[0.3em] uppercase text-glow-sm">Guides</span>
      </div>
      <h1 className="text-4xl md:text-5xl font-bold text-foreground tracking-tight mb-4">
        FastAPI Integration
      </h1>
      <p className="text-muted-foreground text-base leading-relaxed max-w-xl mb-12">
        Reference pattern for a FastAPI chatbot: ingest user signal, retrieve context, answer, ingest assistant output, record feedback.
      </p>
      <p className="text-muted-foreground text-sm leading-relaxed mb-6">
        Orbit Cloud users can create API keys in <a href="/dashboard" className="text-primary hover:underline">Dashboard</a>. Replace <code className="text-primary">{"<jwt-token>"}</code> below with your <code className="text-primary">orbit_pk_...</code> key.
      </p>

      <CodeBlock
        code={`from fastapi import FastAPI
from orbit import MemoryEngine

app = FastAPI()
orbit = MemoryEngine(api_key="<jwt-token>", base_url="http://localhost:8000")

@app.post("/chat")
async def chat(user_id: str, message: str) -> dict[str, str]:
    orbit.ingest(
        content=message,
        event_type="user_question",
        entity_id=user_id,
    )

    context = orbit.retrieve(
        query=f"What should I know about {user_id} for: {message}",
        entity_id=user_id,
        limit=5,
    )

    prompt_context = "\\n".join(f"- {m.content}" for m in context.memories)
    answer = f"(LLM answer using context)\\n{prompt_context}"

    orbit.ingest(
        content=answer,
        event_type="assistant_response",
        entity_id=user_id,
    )
    return {"response": answer}

@app.post("/feedback")
async def feedback(memory_id: str, helpful: bool) -> dict[str, bool]:
    orbit.feedback(
        memory_id=memory_id,
        helpful=helpful,
        outcome_value=1.0 if helpful else -1.0,
    )
    return {"recorded": True}`}
        language="python"
        filename="main.py"
      />

      <div className="border border-primary/30 bg-primary/5 p-6 my-12">
        <h3 className="text-sm font-bold text-primary mb-2">Integration guardrails</h3>
        <div className="space-y-2">
          {[
            "Ingest user and assistant events with the same entity_id scope.",
            "Keep retrieve limit small first (5 to 10) and measure quality.",
            "Record feedback for both successful and poor responses.",
            "Inspect provenance metadata during QA to explain ranking behavior.",
          ].map((tip, i) => (
            <div key={i} className="flex items-start gap-2">
              <span className="text-primary text-xs mt-0.5">{">"}</span>
              <p className="text-xs text-muted-foreground leading-relaxed">{tip}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="border-t border-border pt-8">
        <p className="text-xs text-muted-foreground tracking-wider uppercase mb-2">Next</p>
        <a href="/docs/openclaw-plugin" className="text-foreground hover:text-primary transition-colors font-bold">
          OpenClaw Plugin {"->"}
        </a>
      </div>
    </div>
  )
}
