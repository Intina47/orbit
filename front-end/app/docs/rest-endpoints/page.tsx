import { CodeBlock } from "@/components/orbit/code-block"

export default function RestEndpointsPage() {
  return (
    <div>
      <div className="flex items-center gap-3 mb-6">
        <div className="w-8 h-px bg-primary" />
        <span className="text-primary text-xs tracking-[0.3em] uppercase text-glow-sm">API</span>
      </div>
      <h1 className="text-4xl md:text-5xl font-bold text-foreground tracking-tight mb-4">
        REST Endpoints
      </h1>
      <p className="text-muted-foreground text-base leading-relaxed max-w-xl mb-12">
        Curl-first examples for Orbit endpoints. Protected routes require Bearer JWT or Orbit API key.
      </p>
      <div className="border border-primary/30 bg-primary/5 p-6 mb-12">
        <h3 className="text-sm font-bold text-primary mb-2">Credential source</h3>
        <p className="text-xs text-muted-foreground leading-relaxed">
          Orbit Cloud users should create keys in <a href="/dashboard" className="text-primary hover:underline">Dashboard</a> and replace <code className="text-primary">{"<jwt-token>"}</code> with <code className="text-primary">orbit_pk_...</code>. Self-hosted users can keep JWT.
        </p>
        <p className="text-xs text-muted-foreground leading-relaxed mt-2">
          Need full non-SDK app examples? See <a href="/docs/examples" className="text-primary hover:underline">Direct API (No SDK)</a> for Node.js, Python, and Go samples.
        </p>
      </div>

      {/* Ingest */}
      <h2 className="text-2xl font-bold text-foreground mb-4">POST /v1/ingest</h2>
      <CodeBlock
        code={`curl -X POST http://localhost:8000/v1/ingest \\
  -H "Authorization: Bearer <jwt-token>" \\
  -H "Idempotency-Key: ingest-alice-0001" \\
  -H "Content-Type: application/json" \\
  -d '{
    "content": "I keep confusing while loops and for loops",
    "event_type": "user_question",
    "entity_id": "alice"
  }'`}
        language="bash"
        filename="ingest.sh"
      />

      {/* Retrieve */}
      <h2 className="text-2xl font-bold text-foreground mb-4 mt-12">GET /v1/retrieve</h2>
      <CodeBlock
        code={`curl "http://localhost:8000/v1/retrieve?query=What%20should%20I%20know%20about%20alice?&entity_id=alice&limit=5" \\
  -H "Authorization: Bearer <jwt-token>"`}
        language="bash"
        filename="retrieve.sh"
      />

      {/* Feedback */}
      <h2 className="text-2xl font-bold text-foreground mb-4 mt-12">POST /v1/feedback</h2>
      <CodeBlock
        code={`curl -X POST http://localhost:8000/v1/feedback \\
  -H "Authorization: Bearer <jwt-token>" \\
  -H "Idempotency-Key: feedback-alice-0001" \\
  -H "Content-Type: application/json" \\
  -d '{"memory_id": "<memory-id>", "helpful": true, "outcome_value": 1.0}'`}
        language="bash"
        filename="feedback.sh"
      />

      {/* Batch ingest */}
      <h2 className="text-2xl font-bold text-foreground mb-4 mt-12">POST /v1/ingest/batch</h2>
      <CodeBlock
        code={`curl -X POST http://localhost:8000/v1/ingest/batch \\
  -H "Authorization: Bearer <jwt-token>" \\
  -H "Idempotency-Key: ingest-batch-001" \\
  -H "Content-Type: application/json" \\
  -d '{"events": [
    {"content": "Lesson 1 complete", "event_type": "learning_progress", "entity_id": "alice"},
    {"content": "Lesson 2 complete", "event_type": "learning_progress", "entity_id": "alice"}
  ]}'`}
        language="bash"
        filename="ingest-batch.sh"
      />

      {/* Health */}
      <h2 className="text-2xl font-bold text-foreground mb-4 mt-12">GET /v1/health</h2>
      <CodeBlock
        code={`curl http://localhost:8000/v1/health`}
        language="bash"
        filename="health.sh"
      />

      {/* Status */}
      <h2 className="text-2xl font-bold text-foreground mb-4 mt-12">GET /v1/status</h2>
      <p className="text-muted-foreground text-sm leading-relaxed mb-4">
        Returns account usage, storage footprint, and quota counters.
      </p>
      <CodeBlock
        code={`curl http://localhost:8000/v1/status \\
  -H "Authorization: Bearer <jwt-token>"`}
        language="bash"
        filename="status.sh"
      />

      {/* Dashboard keys */}
      <h2 className="text-2xl font-bold text-foreground mb-4 mt-12">POST /v1/dashboard/keys</h2>
      <CodeBlock
        code={`curl -X POST http://localhost:8000/v1/dashboard/keys \\
  -H "Authorization: Bearer <jwt-token>" \\
  -H "Content-Type: application/json" \\
  -d '{"name":"frontend-prod","scopes":["read","write","feedback"]}'`}
        language="bash"
        filename="dashboard-issue.sh"
      />

      <h2 className="text-2xl font-bold text-foreground mb-4 mt-12">GET /v1/dashboard/keys</h2>
      <CodeBlock
        code={`curl "http://localhost:8000/v1/dashboard/keys?limit=10" \\
  -H "Authorization: Bearer <jwt-token>"`}
        language="bash"
        filename="dashboard-list.sh"
      />

      <h2 className="text-2xl font-bold text-foreground mb-4 mt-12">POST /v1/dashboard/keys/{'{key_id}'}/rotate</h2>
      <CodeBlock
        code={`curl -X POST http://localhost:8000/v1/dashboard/keys/<key-id>/rotate \\
  -H "Authorization: Bearer <jwt-token>" \\
  -H "Content-Type: application/json" \\
  -d '{"name":"frontend-prod-rotated","scopes":["read","write","feedback"]}'`}
        language="bash"
        filename="dashboard-rotate.sh"
      />

      <h2 className="text-2xl font-bold text-foreground mb-4 mt-12">POST /v1/dashboard/keys/{'{key_id}'}/revoke</h2>
      <CodeBlock
        code={`curl -X POST http://localhost:8000/v1/dashboard/keys/<key-id>/revoke \\
  -H "Authorization: Bearer <jwt-token>"`}
        language="bash"
        filename="dashboard-revoke.sh"
      />

      {/* Metrics */}
      <h2 className="text-2xl font-bold text-foreground mb-4 mt-12">GET /v1/metrics</h2>
      <p className="text-muted-foreground text-sm leading-relaxed mb-4">
        Prometheus scrape endpoint for runtime and API metrics.
      </p>
      <CodeBlock
        code={`curl http://localhost:8000/v1/metrics`}
        language="bash"
        filename="metrics.sh"
      />

      <div className="border-t border-border pt-8 mt-12">
        <p className="text-xs text-muted-foreground tracking-wider uppercase mb-2">Next</p>
        <a href="/docs/fastapi-integration" className="text-foreground hover:text-primary transition-colors font-bold">
          FastAPI Integration {"->"}
        </a>
      </div>
    </div>
  )
}
