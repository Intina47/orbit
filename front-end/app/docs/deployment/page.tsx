import { CodeBlock } from "@/components/orbit/code-block"

export default function DeploymentPage() {
  return (
    <div>
      <div className="flex items-center gap-3 mb-6">
        <div className="w-8 h-px bg-primary" />
        <span className="text-primary text-xs tracking-[0.3em] uppercase text-glow-sm">Operations</span>
      </div>
      <h1 className="text-4xl md:text-5xl font-bold text-foreground tracking-tight mb-4">
        Deployment
      </h1>
      <p className="text-muted-foreground text-base leading-relaxed max-w-xl mb-12">
        Run Orbit locally with Docker Compose, then promote the same topology to production.
      </p>

      {/* Stack */}
      <h2 className="text-2xl font-bold text-foreground mb-4">Runtime stack</h2>
      <div className="grid grid-cols-1 gap-px bg-border mb-12">
        {[
          { name: "Orbit API", desc: "Core API service (src/orbit_api/)" },
          { name: "PostgreSQL", desc: "Default runtime database" },
          { name: "Prometheus", desc: "Scrapes /v1/metrics" },
          { name: "OpenTelemetry", desc: "OTLP collector for traces" },
        ].map((item) => (
          <div key={item.name} className="bg-background p-4 flex items-center justify-between">
            <span className="text-sm text-foreground font-bold">{item.name}</span>
            <span className="text-xs text-muted-foreground">{item.desc}</span>
          </div>
        ))}
      </div>

      {/* Local deployment */}
      <h2 className="text-2xl font-bold text-foreground mb-4">Local deployment</h2>
      <CodeBlock code="docker compose up --build" language="bash" filename="terminal" />

      {/* Migrations */}
      <h2 className="text-2xl font-bold text-foreground mb-4 mt-12">Migrations</h2>
      <p className="text-muted-foreground text-sm leading-relaxed mb-4">
        Alembic migrations live in <code className="text-primary">migrations/</code>. Run on deploy or enable startup auto-migrate.
      </p>
      <CodeBlock code="python -m alembic upgrade head" language="bash" filename="terminal" />
      <p className="text-muted-foreground text-sm leading-relaxed mt-4 mb-4">
        Optional startup migration flag:
      </p>
      <CodeBlock code="ORBIT_AUTO_MIGRATE=true" language="bash" filename=".env" />

      {/* Required env vars */}
      <h2 className="text-2xl font-bold text-foreground mb-6 mt-12">Required environment variables</h2>
      <div className="grid grid-cols-1 gap-px bg-border mb-12">
        {[
          { var: "MDE_DATABASE_URL", desc: "PostgreSQL DSN" },
          { var: "ORBIT_JWT_SECRET", desc: "JWT signing secret" },
          { var: "ORBIT_JWT_ISSUER", desc: "Expected JWT issuer" },
          { var: "ORBIT_JWT_AUDIENCE", desc: "Expected JWT audience" },
        ].map((item) => (
          <div key={item.var} className="bg-background p-4 flex items-center justify-between">
            <code className="text-sm text-primary">{item.var}</code>
            <span className="text-xs text-muted-foreground">{item.desc}</span>
          </div>
        ))}
      </div>

      {/* Frontend deployment */}
      <h2 className="text-2xl font-bold text-foreground mb-4">Vercel frontend setup</h2>
      <p className="text-muted-foreground text-sm leading-relaxed mb-4">
        Host the Orbit frontend on Vercel and point it at your Orbit API runtime.
      </p>
      <p className="text-muted-foreground text-sm leading-relaxed mb-4">
        Browser clients never receive Orbit API bearer credentials. Next.js proxy routes exchange dashboard sessions for short-lived tenant-scoped JWTs.
      </p>
      <CodeBlock
        code={`NEXT_PUBLIC_ORBIT_API_BASE_URL=https://orbit-api-ic4qh4dzga-uc.a.run.app
# Optional dashboard CTA destination:
# NEXT_PUBLIC_ORBIT_PILOT_PRO_CONTACT_EMAIL=hello@theorbit.dev
# Optional if different from NEXT_PUBLIC_ORBIT_API_BASE_URL:
# ORBIT_DASHBOARD_PROXY_BASE_URL=https://orbit-api-ic4qh4dzga-uc.a.run.app
ORBIT_DASHBOARD_PROXY_AUTH_MODE=exchange
ORBIT_DASHBOARD_ORBIT_JWT_SECRET=<same-secret-as-orbit-api-jwt-verifier>
# Optional exchange controls:
# ORBIT_DASHBOARD_ORBIT_JWT_ISSUER=orbit
# ORBIT_DASHBOARD_ORBIT_JWT_AUDIENCE=orbit-api
# ORBIT_DASHBOARD_ORBIT_JWT_TTL_SECONDS=300
ORBIT_DASHBOARD_AUTH_MODE=oidc
ORBIT_DASHBOARD_OIDC_GOOGLE_CLIENT_ID=<google-client-id>
ORBIT_DASHBOARD_OIDC_GOOGLE_CLIENT_SECRET=<google-client-secret>
ORBIT_DASHBOARD_OIDC_GITHUB_CLIENT_ID=<github-client-id>
ORBIT_DASHBOARD_OIDC_GITHUB_CLIENT_SECRET=<github-client-secret>
ORBIT_DASHBOARD_SESSION_SECRET=<long-random-secret>
# Optional:
# ORBIT_DASHBOARD_SESSION_TTL_SECONDS=43200
# ORBIT_DASHBOARD_ALLOWED_ORIGINS=https://orbit-memory.vercel.app
# ORBIT_DASHBOARD_ALLOW_MISSING_ORIGIN=false
# ORBIT_DASHBOARD_OIDC_ALLOW_UNSIGNED_ID_TOKEN_FALLBACK=false`}
        language="bash"
        filename="front-end/.env.local"
      />
      <p className="text-muted-foreground text-sm leading-relaxed mt-4 mb-4">
        If frontend and API are on different domains, allow your Vercel origin in backend CORS:
      </p>
      <CodeBlock
        code={`ORBIT_CORS_ALLOW_ORIGINS=https://orbit-memory.vercel.app`}
        language="bash"
        filename="orbit-api.env"
      />
      <p className="text-muted-foreground text-sm leading-relaxed mt-4 mb-4">
        Plan quota controls (Free + invite-only Pilot Pro):
      </p>
      <CodeBlock
        code={`ORBIT_RATE_LIMIT_EVENTS_PER_MONTH=10000
ORBIT_RATE_LIMIT_QUERIES_PER_MONTH=50000
ORBIT_RATE_LIMIT_FREE_API_KEYS=3
ORBIT_RATE_LIMIT_PILOT_PRO_EVENTS_PER_MONTH=250000
ORBIT_RATE_LIMIT_PILOT_PRO_QUERIES_PER_MONTH=1000000
ORBIT_RATE_LIMIT_PILOT_PRO_API_KEYS=25
ORBIT_PILOT_PRO_ACCOUNT_KEYS=acct_team_a,acct_team_b
ORBIT_USAGE_WARNING_THRESHOLD_PERCENT=80
ORBIT_USAGE_CRITICAL_THRESHOLD_PERCENT=95`}
        language="bash"
        filename="orbit-api.env"
      />

      {/* Production checklist */}
      <h2 className="text-2xl font-bold text-foreground mb-4">Production checklist</h2>
      <div className="space-y-3 mb-12">
        {[
          "JWT issuer/audience/secret configured with non-default secrets.",
          "PostgreSQL backups and retention policy enabled.",
          "Prometheus scraping and alerting configured.",
          "OTel exporter endpoint connected to your tracing backend.",
          "SLO alerts on latency, 401, 429, and 5xx rates.",
          "Migration command integrated in CI/CD release flow.",
          "Integration tests cover ingest -> retrieve -> feedback loop.",
          "Vercel frontend env vars are configured and CORS allows your Vercel origin.",
        ].map((item, i) => (
          <div key={i} className="flex items-start gap-3">
            <div className="w-5 h-5 border border-border flex items-center justify-center shrink-0 mt-0.5">
              <span className="text-xs text-muted-foreground">{i + 1}</span>
            </div>
            <p className="text-sm text-muted-foreground leading-relaxed">{item}</p>
          </div>
        ))}
      </div>

      <div className="border-t border-border pt-8">
        <p className="text-xs text-muted-foreground tracking-wider uppercase mb-2">Next</p>
        <a href="/docs/configuration" className="text-foreground hover:text-primary transition-colors font-bold">
          Configuration {"->"}
        </a>
      </div>
    </div>
  )
}
