export default function ApiReferencePage() {
  const sdkMethods = [
    { method: "ingest(content, event_type?, metadata?, entity_id?)", returns: "IngestResponse", desc: "Write one memory event" },
    { method: "retrieve(query, limit?, entity_id?, event_type?, time_range?)", returns: "RetrieveResponse", desc: "Fetch ranked memory context" },
    { method: "feedback(memory_id, helpful, outcome_value?)", returns: "FeedbackResponse", desc: "Send outcome signal for learning" },
    { method: "status()", returns: "StatusResponse", desc: "Usage, storage, quota status" },
    { method: "ingest_batch(events)", returns: "list[IngestResponse]", desc: "Batch ingest for throughput" },
    { method: "feedback_batch(feedback)", returns: "list[FeedbackResponse]", desc: "Batch feedback writes" },
  ]

  const endpoints = [
    { method: "POST", path: "/v1/ingest", desc: "Store one memory event" },
    { method: "GET", path: "/v1/retrieve", desc: "Retrieve ranked memories" },
    { method: "POST", path: "/v1/feedback", desc: "Store feedback signal" },
    { method: "POST", path: "/v1/ingest/batch", desc: "Batch event ingest" },
    { method: "POST", path: "/v1/feedback/batch", desc: "Batch feedback ingest" },
    { method: "GET", path: "/v1/status", desc: "Quota and storage visibility" },
    { method: "GET", path: "/v1/health", desc: "Health/liveness check" },
    { method: "GET", path: "/v1/metrics", desc: "Prometheus metrics" },
    { method: "GET", path: "/v1/memories", desc: "List stored memories" },
    { method: "POST", path: "/v1/auth/validate", desc: "JWT validation endpoint" },
    { method: "POST", path: "/v1/dashboard/keys", desc: "Issue API key (returns plaintext once)" },
    { method: "GET", path: "/v1/dashboard/keys", desc: "List keys (paginated)" },
    { method: "POST", path: "/v1/dashboard/keys/{key_id}/revoke", desc: "Revoke one key" },
    { method: "POST", path: "/v1/dashboard/keys/{key_id}/rotate", desc: "Rotate key (create new + revoke old)" },
  ]

  return (
    <div>
      <div className="flex items-center gap-3 mb-6">
        <div className="w-8 h-px bg-primary" />
        <span className="text-primary text-xs tracking-[0.3em] uppercase text-glow-sm">
          API
        </span>
      </div>
      <h1 className="text-4xl md:text-5xl font-bold text-foreground tracking-tight mb-4">
        API Reference
      </h1>
      <p className="text-muted-foreground text-base leading-relaxed max-w-xl mb-12">
        Orbit exposes the same core loop in SDK and REST form: ingest, retrieve, feedback, status.
      </p>

      {/* Auth */}
      <div className="border border-primary/30 bg-primary/5 p-6 mb-12">
        <h3 className="text-sm font-bold text-primary mb-2">Authentication</h3>
        <p className="text-xs text-muted-foreground leading-relaxed mb-3">
          All protected endpoints require <code className="text-primary">Authorization: Bearer {'<token>'}</code> (JWT or Orbit API key).
        </p>
        <p className="text-xs text-muted-foreground leading-relaxed mb-3">
          For Orbit Cloud, create/manage API keys in <a href="/dashboard" className="text-primary hover:underline">Dashboard</a>. API key material is shown once at creation/rotation.
        </p>
        <p className="text-xs text-muted-foreground leading-relaxed">
          Required JWT claims: <code className="text-primary">sub</code>, <code className="text-primary">iat</code>, <code className="text-primary">exp</code>, <code className="text-primary">iss</code>, <code className="text-primary">aud</code>. POST endpoints support idempotency via <code className="text-primary">Idempotency-Key</code>. Dashboard key endpoints require write scope (or <code className="text-primary">keys:write</code>).
        </p>
      </div>

      {/* SDK */}
      <h2 className="text-2xl font-bold text-foreground mb-6">SDK methods</h2>
      <p className="text-muted-foreground text-sm leading-relaxed mb-4">
        Sync client: <code className="text-primary">MemoryEngine</code>. Async client: <code className="text-primary">AsyncMemoryEngine</code> with async equivalents.
      </p>
      <div className="border border-border mb-12">
        <div className="grid grid-cols-[1fr_160px_1fr] bg-secondary border-b border-border">
          <div className="px-4 py-3 text-xs font-bold text-muted-foreground tracking-wider uppercase">Method</div>
          <div className="px-4 py-3 text-xs font-bold text-muted-foreground tracking-wider uppercase border-l border-border">Returns</div>
          <div className="px-4 py-3 text-xs font-bold text-muted-foreground tracking-wider uppercase border-l border-border">Description</div>
        </div>
        {sdkMethods.map((item) => (
          <div key={item.method} className="grid grid-cols-[1fr_160px_1fr] border-b border-border last:border-b-0">
            <div className="px-4 py-3">
              <code className="text-primary text-xs break-all">{item.method}</code>
            </div>
            <div className="px-4 py-3 text-xs text-foreground border-l border-border">
              <code>{item.returns}</code>
            </div>
            <div className="px-4 py-3 text-xs text-muted-foreground border-l border-border">{item.desc}</div>
          </div>
        ))}
      </div>

      {/* REST */}
      <h2 className="text-2xl font-bold text-foreground mb-6">REST endpoints</h2>
      <div className="border border-border mb-12">
        <div className="grid grid-cols-[70px_200px_1fr] bg-secondary border-b border-border">
          <div className="px-4 py-3 text-xs font-bold text-muted-foreground tracking-wider uppercase">Method</div>
          <div className="px-4 py-3 text-xs font-bold text-muted-foreground tracking-wider uppercase border-l border-border">Path</div>
          <div className="px-4 py-3 text-xs font-bold text-muted-foreground tracking-wider uppercase border-l border-border">Description</div>
        </div>
        {endpoints.map((item) => (
          <div key={item.path} className="grid grid-cols-[70px_200px_1fr] border-b border-border last:border-b-0">
            <div className="px-4 py-3">
              <span className={`text-xs font-bold ${item.method === "POST" ? "text-primary" : "text-accent"}`}>
                {item.method}
              </span>
            </div>
            <div className="px-4 py-3 border-l border-border">
              <code className="text-sm text-foreground">{item.path}</code>
            </div>
            <div className="px-4 py-3 text-xs text-muted-foreground border-l border-border">{item.desc}</div>
          </div>
        ))}
      </div>

      {/* Rate limit headers */}
      <h2 className="text-2xl font-bold text-foreground mb-4">Rate limit and idempotency headers</h2>
      <div className="space-y-2 mb-12">
        {[
          "X-RateLimit-Limit",
          "X-RateLimit-Remaining",
          "X-RateLimit-Reset",
          "Retry-After (on 429)",
          "X-Idempotency-Replayed (true|false)",
        ].map((header) => (
          <div key={header} className="flex items-center gap-3">
            <span className="text-primary text-sm">{">"}</span>
            <code className="text-sm text-foreground">{header}</code>
          </div>
        ))}
      </div>

      {/* Next */}
      <div className="border-t border-border pt-8">
        <p className="text-xs text-muted-foreground tracking-wider uppercase mb-2">Next</p>
        <a href="/docs/sdk-methods" className="text-foreground hover:text-primary transition-colors font-bold">
          SDK Methods {"->"}
        </a>
      </div>
    </div>
  )
}
