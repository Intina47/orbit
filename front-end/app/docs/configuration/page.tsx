export default function ConfigurationPage() {
  const sections = [
    {
      title: "Core",
      vars: [
        { var: "MDE_DATABASE_URL", desc: "PostgreSQL runtime DSN" },
        { var: "MDE_SQLITE_PATH", desc: "Local fallback path" },
        { var: "MDE_EMBEDDING_DIM", desc: "Embedding dimension" },
      ],
    },
    {
      title: "Provider Selection",
      vars: [
        { var: "MDE_SEMANTIC_PROVIDER", desc: "context | openai | anthropic | gemini | ollama" },
        { var: "MDE_EMBEDDING_PROVIDER", desc: "deterministic | openai | anthropic | gemini | ollama" },
      ],
    },
    {
      title: "Authentication",
      vars: [
        { var: "ORBIT_ENV", desc: "development | production" },
        { var: "ORBIT_JWT_SECRET", desc: "JWT signing secret" },
        { var: "ORBIT_JWT_ISSUER", desc: "Expected issuer claim" },
        { var: "ORBIT_JWT_AUDIENCE", desc: "Expected audience claim" },
        { var: "ORBIT_JWT_ALGORITHM", desc: "JWT signing algorithm" },
        { var: "ORBIT_JWT_REQUIRED_SCOPE", desc: "Optional required scope" },
      ],
    },
    {
      title: "Rate Limits",
      vars: [
        { var: "ORBIT_RATE_LIMIT_PER_MINUTE", desc: "Requests per minute" },
        { var: "ORBIT_DASHBOARD_KEY_RATE_LIMIT_PER_MINUTE", desc: "Dashboard key-management requests per minute" },
        { var: "ORBIT_RATE_LIMIT_EVENTS_PER_DAY", desc: "Daily event quota" },
        { var: "ORBIT_RATE_LIMIT_QUERIES_PER_DAY", desc: "Daily query quota" },
        { var: "ORBIT_MAX_INGEST_CONTENT_CHARS", desc: "Max ingest content length" },
        { var: "ORBIT_MAX_QUERY_CHARS", desc: "Max query length" },
        { var: "ORBIT_MAX_BATCH_ITEMS", desc: "Max items in batch request" },
      ],
    },
    {
      title: "Dashboard/Auth Mapping",
      vars: [
        { var: "ORBIT_DASHBOARD_AUTO_PROVISION_ACCOUNTS", desc: "Auto-create account mapping for new JWT identities" },
        { var: "ORBIT_CORS_ALLOW_ORIGINS", desc: "Comma-separated browser origins allowed to call API directly" },
      ],
    },
    {
      title: "Personalization",
      vars: [
        { var: "MDE_ENABLE_ADAPTIVE_PERSONALIZATION", desc: "Master switch (default: true)" },
        { var: "MDE_PERSONALIZATION_REPEAT_THRESHOLD", desc: "Repeated signals required (default: 3)" },
        { var: "MDE_PERSONALIZATION_SIMILARITY_THRESHOLD", desc: "Semantic similarity threshold (default: 0.82)" },
        { var: "MDE_PERSONALIZATION_WINDOW_DAYS", desc: "Observation window (default: 30)" },
        { var: "MDE_PERSONALIZATION_MIN_FEEDBACK_EVENTS", desc: "Feedback count for preference inference (default: 4)" },
        { var: "MDE_PERSONALIZATION_PREFERENCE_MARGIN", desc: "Preference confidence margin (default: 2.0)" },
      ],
    },
    {
      title: "Observability",
      vars: [
        { var: "ORBIT_OTEL_SERVICE_NAME", desc: "OpenTelemetry service name" },
        { var: "ORBIT_OTEL_EXPORTER_ENDPOINT", desc: "OTLP exporter endpoint" },
      ],
    },
    {
      title: "Frontend (Vercel/Next.js)",
      vars: [
        { var: "NEXT_PUBLIC_ORBIT_API_BASE_URL", desc: "Public API base URL for docs/UI display" },
        { var: "ORBIT_DASHBOARD_PROXY_BASE_URL", desc: "Optional server-side proxy target override" },
        { var: "ORBIT_DASHBOARD_PROXY_AUTH_MODE", desc: "exchange | static" },
        { var: "ORBIT_DASHBOARD_ORBIT_JWT_SECRET", desc: "Exchange-mode JWT signing secret (server only)" },
        { var: "ORBIT_DASHBOARD_ORBIT_JWT_ISSUER", desc: "Exchange-mode JWT issuer claim" },
        { var: "ORBIT_DASHBOARD_ORBIT_JWT_AUDIENCE", desc: "Exchange-mode JWT audience claim" },
        { var: "ORBIT_DASHBOARD_ORBIT_JWT_ALGORITHM", desc: "HS256 | HS384 | HS512" },
        { var: "ORBIT_DASHBOARD_ORBIT_JWT_TTL_SECONDS", desc: "Short-lived proxy JWT TTL (default 300)" },
        { var: "ORBIT_DASHBOARD_SERVER_BEARER_TOKEN", desc: "Static-mode fallback bearer token (legacy)" },
        { var: "ORBIT_DASHBOARD_AUTH_MODE", desc: "password | oidc | disabled" },
        { var: "ORBIT_DASHBOARD_AUTH_PASSWORD", desc: "Password-mode dashboard login secret" },
        { var: "ORBIT_DASHBOARD_OIDC_ISSUER_URL", desc: "OIDC issuer URL for discovery" },
        { var: "ORBIT_DASHBOARD_OIDC_CLIENT_ID", desc: "OIDC client identifier" },
        { var: "ORBIT_DASHBOARD_OIDC_CLIENT_SECRET", desc: "OIDC client secret" },
        { var: "ORBIT_DASHBOARD_OIDC_REDIRECT_URI", desc: "Optional explicit OIDC redirect URI" },
        { var: "ORBIT_DASHBOARD_OIDC_SCOPES", desc: "Optional OIDC scopes string" },
        { var: "ORBIT_DASHBOARD_OIDC_TENANT_CLAIMS", desc: "Optional comma-separated tenant claim keys" },
        { var: "ORBIT_DASHBOARD_ALLOWED_ORIGINS", desc: "Optional CSRF origin allow-list for dashboard mutations" },
        { var: "ORBIT_DASHBOARD_LOGIN_WINDOW_SECONDS", desc: "Password login throttle window" },
        { var: "ORBIT_DASHBOARD_LOGIN_MAX_ATTEMPTS", desc: "Max failed password attempts per window" },
        { var: "ORBIT_DASHBOARD_LOGIN_LOCKOUT_SECONDS", desc: "Password lockout duration after threshold" },
        { var: "ORBIT_DASHBOARD_SESSION_SECRET", desc: "HMAC secret for HTTP-only dashboard session cookie" },
        { var: "ORBIT_DASHBOARD_SESSION_TTL_SECONDS", desc: "Optional session TTL (default 43200)" },
      ],
    },
  ]

  return (
    <div>
      <div className="flex items-center gap-3 mb-6">
        <div className="w-8 h-px bg-primary" />
        <span className="text-primary text-xs tracking-[0.3em] uppercase text-glow-sm">Operations</span>
      </div>
      <h1 className="text-4xl md:text-5xl font-bold text-foreground tracking-tight mb-4">
        Configuration
      </h1>
      <p className="text-muted-foreground text-base leading-relaxed max-w-xl mb-12">
        Environment variable reference for Orbit runtime and SDK behavior. For full defaults, check <code className="text-primary">.env.example</code>.
      </p>

      {sections.map((section) => (
        <div key={section.title} className="mb-12">
          <h2 className="text-xl font-bold text-foreground mb-4">{section.title}</h2>
          <div className="border border-border">
            {section.vars.map((item, i) => (
              <div
                key={item.var}
                className={`p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-2 ${
                  i < section.vars.length - 1 ? "border-b border-border" : ""
                }`}
              >
                <code className="text-sm text-primary break-all">{item.var}</code>
                <span className="text-xs text-muted-foreground">{item.desc}</span>
              </div>
            ))}
          </div>
        </div>
      ))}

      {/* Persistence note */}
      <div className="border border-primary/30 bg-primary/5 p-6 mb-12">
        <h3 className="text-sm font-bold text-primary mb-2">Persistence internals</h3>
        <p className="text-xs text-muted-foreground leading-relaxed">
          Idempotent write state is persisted in <code className="text-primary">api_idempotency</code>. Account quota counters are persisted in <code className="text-primary">api_account_usage</code>.
        </p>
      </div>

      <div className="border-t border-border pt-8">
        <p className="text-xs text-muted-foreground tracking-wider uppercase mb-2">Next</p>
        <a href="/docs/monitoring" className="text-foreground hover:text-primary transition-colors font-bold">
          Monitoring {"->"}
        </a>
      </div>
    </div>
  )
}
