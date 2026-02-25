import Link from "next/link"

const sections = [
  {
    title: "Getting Started",
    description: "Pick Cloud vs Self-Hosted setup, install Orbit, and run your first end-to-end memory loop in minutes.",
    links: [
      { label: "Quickstart", href: "/docs/quickstart" },
      { label: "Installation & Setup Routes", href: "/docs/installation" },
    ],
  },
  {
    title: "Core Concepts",
    description: "Understand the contract: event ingestion, retrieval quality, feedback signals, and inferred memory.",
    links: [
      { label: "Integration Guide", href: "/docs/integration-guide" },
      { label: "Event Taxonomy", href: "/docs/event-taxonomy" },
      { label: "Personalization", href: "/docs/personalization" },
    ],
  },
  {
    title: "API Reference",
    description: "Method-by-method SDK docs and endpoint-by-endpoint REST reference.",
    links: [
      { label: "API Reference", href: "/docs/api-reference" },
      { label: "SDK Methods", href: "/docs/sdk-methods" },
      { label: "REST Endpoints", href: "/docs/rest-endpoints" },
    ],
  },
  {
    title: "Guides",
    description: "Production-style examples for FastAPI, OpenClaw integration, and live chatbot testing.",
    links: [
      { label: "FastAPI Integration", href: "/docs/fastapi-integration" },
      { label: "OpenClaw Plugin", href: "/docs/openclaw-plugin" },
      { label: "Examples", href: "/docs/examples" },
    ],
  },
  {
    title: "Operations",
    description: "Deploy, configure, monitor, and troubleshoot Orbit with a Postgres-first runtime path.",
    links: [
      { label: "Cloud Dashboard", href: "/dashboard" },
      { label: "Deployment", href: "/docs/deployment" },
      { label: "Configuration", href: "/docs/configuration" },
      { label: "Monitoring", href: "/docs/monitoring" },
      { label: "Troubleshooting", href: "/docs/troubleshooting" },
    ],
  },
]

export default function DocsOverview() {
  return (
    <div>
      {/* Header */}
      <div className="mb-16">
        <div className="flex items-center gap-3 mb-6">
          <div className="w-8 h-px bg-primary" />
          <span className="text-primary text-xs tracking-[0.3em] uppercase text-glow-sm">
            Documentation
          </span>
        </div>
        <h1 className="text-4xl md:text-5xl font-bold text-foreground tracking-tight mb-6">
          Orbit Developer Docs
        </h1>
        <p className="text-muted-foreground text-base md:text-lg leading-relaxed max-w-xl">
          Orbit is memory infrastructure for developer-facing AI products. Send signals, retrieve focused context, close the loop with feedback, and let memory quality improve over time.
        </p>
      </div>

      {/* Quick install */}
      <div className="border border-border mb-16">
        <div className="bg-secondary px-4 py-2 border-b border-border">
          <span className="text-xs text-muted-foreground">terminal</span>
        </div>
        <div className="p-4">
          <code className="text-primary text-sm">pip install orbit-memory</code>
        </div>
      </div>

      <div className="border border-primary/30 bg-primary/5 p-4 mb-16">
        <p className="text-xs text-muted-foreground leading-relaxed">
          Need code generated for your stack? Use the floating <span className="text-primary font-semibold">Setup with AI</span> button on this page to build a ready-to-paste prompt for ChatGPT, Claude, or Cursor.
        </p>
      </div>

      {/* Section grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-px bg-border">
        {sections.map((section) => (
          <div key={section.title} className="bg-background p-8">
            <div className="flex items-center gap-2 mb-3">
              <div className="w-4 h-px bg-primary" />
              <h2 className="text-xs tracking-[0.3em] uppercase text-muted-foreground font-bold">
                {section.title}
              </h2>
            </div>
            <p className="text-sm text-muted-foreground leading-relaxed mb-6">
              {section.description}
            </p>
            <div className="space-y-2">
              {section.links.map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  className="flex items-center gap-2 text-sm text-foreground hover:text-primary transition-colors group"
                >
                  <span className="text-muted-foreground group-hover:text-primary transition-colors">
                    {">"}
                  </span>
                  {link.label}
                </Link>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
