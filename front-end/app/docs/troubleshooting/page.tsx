export default function TroubleshootingPage() {
  const issues = [
    {
      code: "401",
      title: "Unauthorized",
      fixes: [
        "Verify Bearer token is a valid JWT signed with ORBIT_JWT_SECRET.",
        "Confirm token includes sub, iat, exp, iss, and aud claims.",
        "Check iss and aud values match ORBIT_JWT_ISSUER and ORBIT_JWT_AUDIENCE.",
        "Check expiration and server clock skew.",
      ],
    },
    {
      code: "429",
      title: "Rate Limit Exceeded",
      fixes: [
        "Read Retry-After before retrying.",
        "Enable SDK retries with exponential backoff.",
        "Tune call volume or adjust configured limits.",
      ],
    },
    {
      code: "409",
      title: "Idempotency Conflict",
      fixes: [
        "Same Idempotency-Key was reused with a different payload.",
        "Use a unique key per unique request body.",
      ],
    },
    {
      code: "---",
      title: "Timeout Errors",
      fixes: [
        "Verify API health via GET /v1/health.",
        "Increase timeout_seconds in SDK config.",
        "Check network path, especially when running through local tunnels or proxies.",
      ],
    },
    {
      code: "---",
      title: "Empty Retrieval Results",
      fixes: [
        "Confirm ingest responses return stored=True.",
        "Ensure entity_id is consistent between ingest and retrieve.",
        "Use concrete queries instead of broad prompts.",
        "Validate event taxonomy consistency.",
      ],
    },
    {
      code: "---",
      title: "No Personalization Signal",
      fixes: [
        "Check MDE_ENABLE_ADAPTIVE_PERSONALIZATION=true.",
        "Use a stable entity_id for repeated-user interactions.",
        "Generate enough repeated signals for threshold crossing.",
        "Send enough feedback events for preference inference.",
      ],
    },
    {
      code: "---",
      title: "Noisy Top Results",
      fixes: [
        "Record negative feedback for unhelpful memories.",
        "Audit long assistant outputs that may crowd concise profile facts.",
        "Review inference provenance metadata to understand ranking behavior.",
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
        Troubleshooting
      </h1>
      <p className="text-muted-foreground text-base leading-relaxed max-w-xl mb-12">
        Common failure modes and practical fixes. No mystery theater.
      </p>

      <div className="space-y-8">
        {issues.map((issue) => (
          <div key={issue.title} className="border border-border">
            <div className="flex items-center gap-4 bg-secondary px-6 py-4 border-b border-border">
              {issue.code !== "---" && (
                <span className="text-destructive text-sm font-bold">{issue.code}</span>
              )}
              <h2 className="text-sm font-bold text-foreground">{issue.title}</h2>
            </div>
            <div className="p-6 space-y-3">
              {issue.fixes.map((fix, i) => (
                <div key={i} className="flex items-start gap-3">
                  <span className="text-primary text-sm mt-0.5">{">"}</span>
                  <p className="text-sm text-muted-foreground leading-relaxed">{fix}</p>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* Dev validation */}
      <h2 className="text-2xl font-bold text-foreground mb-4 mt-12">Developer validation checklist</h2>
      <p className="text-muted-foreground text-sm leading-relaxed mb-4">
        Run quality gates before release:
      </p>
      <div className="border border-border">
        {[
          "python -m ruff check src tests examples scripts",
          "python -m mypy src",
          "python -m pytest -q",
          "python -m pylint src tests scripts --fail-under=9.0",
        ].map((cmd, i, arr) => (
          <div key={cmd} className={`p-4 ${i < arr.length - 1 ? "border-b border-border" : ""}`}>
            <code className="text-sm text-primary">{cmd}</code>
          </div>
        ))}
      </div>

      <div className="border-t border-border pt-8 mt-12">
        <p className="text-xs text-muted-foreground tracking-wider uppercase mb-2">Back to</p>
        <a href="/docs" className="text-foreground hover:text-primary transition-colors font-bold">
          Documentation Overview {"->"}
        </a>
      </div>
    </div>
  )
}
