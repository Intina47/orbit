import Link from "next/link"

const keywords = [
  "memory for developers",
  "semantic retrieval",
  "contradiction guard",
  "adaptive personalization",
  "metadata provenance",
  "LLM adapters",
  "fact inference",
  "conflict-aware decay",
]

const libraries = [
  "orbit-memory (SDK)",
  "Anthropic / Gemini / Ollama adapters",
  "FastAPI example chatbot",
  "Resend notifications",
  "OpenClaw plugin slot",
]

const technologies = [
  "PostgreSQL + SQLAlchemy storage",
  "Prometheus + OpenTelemetry + Alertmanager",
  "Render / Cloud Run + Vercel deployment",
  "Docker Compose runtime",
  "Playwright E2E for dashboard",
]

const usagePaths = [
  {
    title: "Local dev",
    detail: "Clone the repo, run `docker compose up`, set `.env.local`, and iterate on prompts.",
  },
  {
    title: "Orbit Cloud",
    detail: "Use hosted API with your API key, skip infra, and focus on delivering memory-aware apps.",
  },
  {
    title: "Pilot Pro polling",
    detail: "Request Pilot Pro for higher quotas; orbit sends a Resend note to the admin email automatically.",
  },
]

export default function MetadataPage() {
  return (
    <div>
      <div className="mb-10">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-8 h-px bg-primary" />
          <span className="text-primary text-xs tracking-[0.3em] uppercase text-glow-sm">
            Metadata
          </span>
        </div>
        <h1 className="text-4xl md:text-5xl font-bold text-foreground tracking-tight mb-4">
          Orbit Thinking &amp; Stack Signals
        </h1>
        <p className="text-sm text-muted-foreground max-w-3xl leading-relaxed">
          This page is the SEO-friendly summary: keywords we repeat, libs we ship, and the technologies we lean on. It keeps our docs consistent and gives AI copilots the language they need to talk about Orbit in a developer-first way.
        </p>
      </div>

      <section className="mb-10">
        <h2 className="text-lg font-semibold text-foreground mb-3">Keywords the docs double down on</h2>
        <div className="flex flex-wrap gap-2">
          {keywords.map((keyword) => (
            <span key={keyword} className="inline-flex items-center px-3 py-1 rounded-full text-xs bg-foreground/5 text-foreground">
              {keyword}
            </span>
          ))}
        </div>
      </section>

      <section className="mb-10">
        <h2 className="text-lg font-semibold text-foreground mb-3">Libraries &amp; adapters</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {libraries.map((lib) => (
            <div key={lib} className="border border-border rounded-2xl p-4 text-sm text-muted-foreground">
              {lib}
            </div>
          ))}
        </div>
      </section>

      <section className="mb-10">
        <h2 className="text-lg font-semibold text-foreground mb-3">Technology stack / infra</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {technologies.map((tech) => (
            <div key={tech} className="border border-border rounded-2xl p-4 text-sm text-muted-foreground">
              {tech}
            </div>
          ))}
        </div>
      </section>

      <section className="mb-10">
        <h2 className="text-lg font-semibold text-foreground mb-3">Usage cue cards for writers</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {usagePaths.map((item) => (
            <div key={item.title} className="bg-background border border-border rounded-2xl p-5">
              <h3 className="text-sm font-semibold text-foreground mb-2">{item.title}</h3>
              <p className="text-xs text-muted-foreground leading-relaxed">{item.detail}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="border-t border-border pt-8">
        <p className="text-xs text-muted-foreground tracking-[0.3em] uppercase mb-3">Need to keep shipping?</p>
        <p className="text-sm text-muted-foreground mb-3">
          Sprinkle this metadata blueprint into the{" "}
          <Link href="/docs/quickstart" className="text-primary hover:underline">
            Quickstart
          </Link>
          ,{" "}
          <Link href="/docs/installation" className="text-primary hover:underline">
            Installation guide
          </Link>
          , and{" "}
          <Link href="/docs/integration-guide" className="text-primary hover:underline">
            Integration Guide
          </Link>{" "}
          so every doc shares the same terminology.
        </p>
      </section>
    </div>
  )
}
