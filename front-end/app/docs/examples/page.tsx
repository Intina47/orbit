export default function ExamplesPage() {
  const examples = [
    { name: "basic_usage.py", desc: "Sync ingest and retrieve flow", path: "examples/basic_usage.py" },
    { name: "async_usage.py", desc: "Async client flow with AsyncMemoryEngine", path: "examples/async_usage.py" },
    { name: "batch_operations.py", desc: "Batch ingest and feedback patterns", path: "examples/batch_operations.py" },
    { name: "agent_integration.py", desc: "Chatbot integration pattern", path: "examples/agent_integration.py" },
    { name: "feedback_loop.py", desc: "Outcome-signal feedback workflow", path: "examples/feedback_loop.py" },
    { name: "personalization_quickstart.py", desc: "Inferred-memory signal flow", path: "examples/personalization_quickstart.py" },
    { name: "live_chatbot_ollama/", desc: "Live Orbit + Ollama coding tutor test stack", path: "examples/live_chatbot_ollama/" },
  ]

  return (
    <div>
      <div className="flex items-center gap-3 mb-6">
        <div className="w-8 h-px bg-primary" />
        <span className="text-primary text-xs tracking-[0.3em] uppercase text-glow-sm">Guides</span>
      </div>
      <h1 className="text-4xl md:text-5xl font-bold text-foreground tracking-tight mb-4">
        Examples
      </h1>
      <p className="text-muted-foreground text-base leading-relaxed max-w-xl mb-12">
        Practical scripts you can run today. Pick one, wire your token, and verify the full memory loop.
      </p>

      <div className="grid grid-cols-1 gap-px bg-border">
        {examples.map((example) => (
          <div key={example.name} className="bg-background p-6">
            <div className="flex items-start justify-between gap-4">
              <div>
                <code className="text-sm text-primary font-bold">{example.name}</code>
                <p className="text-xs text-muted-foreground mt-2">{example.desc}</p>
              </div>
              <code className="text-xs text-muted-foreground shrink-0">{example.path}</code>
            </div>
          </div>
        ))}
      </div>

      <div className="border border-primary/30 bg-primary/5 p-6 mt-12">
        <h3 className="text-sm font-bold text-primary mb-2">Tip for first-time evals</h3>
        <p className="text-xs text-muted-foreground leading-relaxed">
          Start with <code className="text-primary">live_chatbot_ollama/</code> and test repeated-user scenarios over several sessions. Memory quality differences show up in day-2 and day-7 behavior, not only the first chat.
        </p>
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
