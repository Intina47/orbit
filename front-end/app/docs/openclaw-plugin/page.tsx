import { CodeBlock } from "@/components/orbit/code-block"

export default function OpenClawPluginPage() {
  return (
    <div>
      <div className="flex items-center gap-3 mb-6">
        <div className="w-8 h-px bg-primary" />
        <span className="text-primary text-xs tracking-[0.3em] uppercase text-glow-sm">Guides</span>
      </div>
      <h1 className="text-4xl md:text-5xl font-bold text-foreground tracking-tight mb-4">
        OpenClaw Plugin
      </h1>
      <p className="text-muted-foreground text-base leading-relaxed max-w-xl mb-12">
        Orbit ships an OpenClaw plugin scaffold so agent memory tools can run against Orbit without custom adapter glue.
      </p>

      <h2 className="text-2xl font-bold text-foreground mb-4">Plugin details</h2>
      <div className="grid grid-cols-1 gap-px bg-border mb-12">
        <div className="bg-background p-4 flex items-center justify-between">
          <span className="text-sm text-muted-foreground">Plugin manifest</span>
          <code className="text-xs text-primary">integrations/openclaw-memory/openclaw.plugin.json</code>
        </div>
        <div className="bg-background p-4 flex items-center justify-between">
          <span className="text-sm text-muted-foreground">Package name</span>
          <code className="text-xs text-primary">@orbit/openclaw-memory</code>
        </div>
        <div className="bg-background p-4 flex items-center justify-between">
          <span className="text-sm text-muted-foreground">Source directory</span>
          <code className="text-xs text-primary">integrations/openclaw-memory/</code>
        </div>
      </div>

      <h2 className="text-2xl font-bold text-foreground mb-4">Build</h2>
      <CodeBlock
        code={`cd integrations/openclaw-memory
npm install
npm run build`}
        language="bash"
        filename="terminal"
      />

      <h2 className="text-2xl font-bold text-foreground mb-4 mt-12">Required environment</h2>
      <div className="grid grid-cols-1 gap-px bg-border mb-12">
        <div className="bg-background p-4 flex items-center justify-between">
          <code className="text-sm text-primary">ORBIT_API_URL</code>
          <span className="text-xs text-muted-foreground">default: http://127.0.0.1:8000</span>
        </div>
        <div className="bg-background p-4 flex items-center justify-between">
          <code className="text-sm text-primary">ORBIT_JWT_TOKEN</code>
          <span className="text-xs text-muted-foreground">JWT for Orbit API access</span>
        </div>
      </div>

      <h2 className="text-2xl font-bold text-foreground mb-4">Exposed surfaces</h2>
      <div className="space-y-3 mb-12">
        {[
          { type: "tool", name: "orbit_recall", desc: "Retrieve ranked memories from Orbit" },
          { type: "tool", name: "orbit_feedback", desc: "Write helpful/unhelpful outcome signals" },
          { type: "command", name: "orbit-memory-status", desc: "Check runtime and quota status" },
        ].map((item) => (
          <div key={item.name} className="flex items-start gap-4 p-4 border border-border">
            <span className="text-xs text-muted-foreground tracking-wider uppercase w-16">{item.type}</span>
            <div>
              <code className="text-sm text-primary font-bold">{item.name}</code>
              <p className="text-xs text-muted-foreground mt-1">{item.desc}</p>
            </div>
          </div>
        ))}
      </div>

      <div className="border border-primary/30 bg-primary/5 p-6 mb-12">
        <h3 className="text-sm font-bold text-primary mb-2">Recommended rollout</h3>
        <p className="text-xs text-muted-foreground leading-relaxed">
          Start by routing recall through Orbit while keeping existing logging in place. Once retrieval quality and latency pass your gates, route memory feedback and CLI memory commands fully through the plugin.
        </p>
      </div>

      <div className="border-t border-border pt-8">
        <p className="text-xs text-muted-foreground tracking-wider uppercase mb-2">Next</p>
        <a href="/docs/examples" className="text-foreground hover:text-primary transition-colors font-bold">
          Examples {"->"}
        </a>
      </div>
    </div>
  )
}
