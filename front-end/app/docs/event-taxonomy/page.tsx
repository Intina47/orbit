export default function EventTaxonomyPage() {
  const events = [
    { type: "user_question", meaning: "User asks for help, clarification, or explanation" },
    { type: "assistant_response", meaning: "Assistant output delivered to user" },
    { type: "learning_progress", meaning: "Milestone completion or skill advancement" },
    { type: "assessment_result", meaning: "Quiz, test, or evaluation outcome" },
    { type: "user_attempt", meaning: "User attempt at a task, prompt, or exercise" },
    { type: "preference_stated", meaning: "Explicit user preference (style, pacing, format)" },
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
        Event Taxonomy
      </h1>
      <p className="text-muted-foreground text-base leading-relaxed max-w-xl mb-12">
        Good memory starts with clean event semantics. Keep event names stable and meaningful across your product.
      </p>

      {/* Table */}
      <div className="border border-border mb-12">
        <div className="grid grid-cols-[200px_1fr] bg-secondary border-b border-border">
          <div className="px-4 py-3 text-xs font-bold text-muted-foreground tracking-wider uppercase">
            Event Type
          </div>
          <div className="px-4 py-3 text-xs font-bold text-muted-foreground tracking-wider uppercase border-l border-border">
            Meaning
          </div>
        </div>
        {events.map((event) => (
          <div key={event.type} className="grid grid-cols-[200px_1fr] border-b border-border last:border-b-0">
            <div className="px-4 py-3">
              <code className="text-primary text-sm">{event.type}</code>
            </div>
            <div className="px-4 py-3 text-sm text-muted-foreground border-l border-border">
              {event.meaning}
            </div>
          </div>
        ))}
      </div>

      {/* Inferred types */}
      <h2 className="text-2xl font-bold text-foreground mb-4">Inferred memory types</h2>
      <p className="text-muted-foreground text-sm leading-relaxed mb-6">
        Orbit can also create inferred memories when evidence is strong enough.
      </p>

      <div className="grid grid-cols-1 gap-px bg-border mb-12">
        <div className="bg-background p-6">
          <code className="text-primary text-sm font-bold">inferred_learning_pattern</code>
          <p className="text-xs text-muted-foreground mt-2 leading-relaxed">
            Generated from repeated semantically similar behavior for the same entity. Example: a learner repeatedly asks loop-control questions.
          </p>
        </div>
        <div className="bg-background p-6">
          <code className="text-primary text-sm font-bold">inferred_preference</code>
          <p className="text-xs text-muted-foreground mt-2 leading-relaxed">
            Generated from sustained feedback trends. Example: concise answers consistently receive higher helpfulness scores.
          </p>
        </div>
      </div>

      <div className="border border-primary/30 bg-primary/5 p-6 mb-12">
        <h3 className="text-sm font-bold text-primary mb-2">Taxonomy rule of thumb</h3>
        <p className="text-xs text-muted-foreground leading-relaxed">
          If two events represent meaningfully different behaviors, give them different event types. If not, keep one type and use metadata fields for detail.
        </p>
      </div>

      {/* Next */}
      <div className="border-t border-border pt-8">
        <p className="text-xs text-muted-foreground tracking-wider uppercase mb-2">Next</p>
        <a href="/docs/personalization" className="text-foreground hover:text-primary transition-colors font-bold">
          Personalization {"->"}
        </a>
      </div>
    </div>
  )
}
