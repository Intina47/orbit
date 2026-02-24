export default function MonitoringPage() {
  return (
    <div>
      <div className="flex items-center gap-3 mb-6">
        <div className="w-8 h-px bg-primary" />
        <span className="text-primary text-xs tracking-[0.3em] uppercase text-glow-sm">Operations</span>
      </div>
      <h1 className="text-4xl md:text-5xl font-bold text-foreground tracking-tight mb-4">
        Monitoring
      </h1>
      <p className="text-muted-foreground text-base leading-relaxed max-w-xl mb-12">
        Use health checks, metrics, and traces to keep Orbit predictable in production.
      </p>

      {/* Health */}
      <h2 className="text-2xl font-bold text-foreground mb-4">Health check</h2>
      <div className="border border-border p-4 mb-8">
        <div className="flex items-center gap-3">
          <span className="text-accent text-xs font-bold">GET</span>
          <code className="text-sm text-foreground">/v1/health</code>
        </div>
        <p className="text-xs text-muted-foreground mt-2">Use as liveness probe. Keep it cheap and frequent.</p>
      </div>

      {/* Metrics */}
      <h2 className="text-2xl font-bold text-foreground mb-4">Prometheus metrics</h2>
      <div className="grid grid-cols-1 gap-px bg-border mb-8">
        <div className="bg-background p-4 flex items-center justify-between">
          <code className="text-sm text-foreground">GET /v1/metrics</code>
          <span className="text-xs text-muted-foreground">Prometheus format output</span>
        </div>
        <div className="bg-background p-4 flex items-center justify-between">
          <span className="text-sm text-foreground">Prometheus UI</span>
          <code className="text-xs text-primary">http://localhost:9090</code>
        </div>
      </div>

      {/* Status */}
      <h2 className="text-2xl font-bold text-foreground mb-4">Status endpoint</h2>
      <div className="border border-border p-4 mb-8">
        <div className="flex items-center gap-3">
          <span className="text-accent text-xs font-bold">GET</span>
          <code className="text-sm text-foreground">/v1/status</code>
        </div>
        <p className="text-xs text-muted-foreground mt-2">Returns usage, storage footprint, and quota counters for the caller.</p>
      </div>

      {/* Rate limit headers */}
      <h2 className="text-2xl font-bold text-foreground mb-4">Rate limit and replay headers</h2>
      <div className="border border-border mb-12">
        {[
          { header: "X-RateLimit-Limit", desc: "Maximum requests allowed" },
          { header: "X-RateLimit-Remaining", desc: "Requests remaining in current window" },
          { header: "X-RateLimit-Reset", desc: "Window reset timestamp" },
          { header: "Retry-After", desc: "Retry delay in seconds (on 429)" },
          { header: "X-Idempotency-Replayed", desc: "Whether response came from idempotency replay" },
        ].map((item, i, arr) => (
          <div key={item.header} className={`p-4 flex items-center justify-between ${i < arr.length - 1 ? "border-b border-border" : ""}`}>
            <code className="text-sm text-primary">{item.header}</code>
            <span className="text-xs text-muted-foreground">{item.desc}</span>
          </div>
        ))}
      </div>

      {/* OTel */}
      <h2 className="text-2xl font-bold text-foreground mb-4">OpenTelemetry</h2>
      <div className="grid grid-cols-1 gap-px bg-border mb-12">
        <div className="bg-background p-4 flex items-center justify-between">
          <code className="text-sm text-primary">ORBIT_OTEL_SERVICE_NAME</code>
          <span className="text-xs text-muted-foreground">Logical service name</span>
        </div>
        <div className="bg-background p-4 flex items-center justify-between">
          <code className="text-sm text-primary">ORBIT_OTEL_EXPORTER_ENDPOINT</code>
          <span className="text-xs text-muted-foreground">OTLP exporter destination</span>
        </div>
      </div>

      <div className="border border-primary/30 bg-primary/5 p-6 mb-12">
        <h3 className="text-sm font-bold text-primary mb-2">Practical alerting starter pack</h3>
        <p className="text-xs text-muted-foreground leading-relaxed">
          Alert on sustained 5xx rate, p95 latency regressions, and spikes in 401/429 responses. If your memory API is noisy, your chatbot quality will be noisy too.
        </p>
      </div>

      <div className="border-t border-border pt-8">
        <p className="text-xs text-muted-foreground tracking-wider uppercase mb-2">Next</p>
        <a href="/docs/troubleshooting" className="text-foreground hover:text-primary transition-colors font-bold">
          Troubleshooting {"->"}
        </a>
      </div>
    </div>
  )
}
