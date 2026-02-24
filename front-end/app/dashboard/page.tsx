import { Nav } from "@/components/orbit/nav"
import { DashboardConsole } from "@/components/orbit/dashboard-console"

export default function DashboardPage() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <Nav />
      <main className="max-w-[1400px] mx-auto px-6 md:px-10 py-12 md:py-16">
        <div className="mb-10">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-8 h-px bg-primary" />
            <span className="text-primary text-xs tracking-[0.3em] uppercase text-glow-sm">
              Orbit Cloud
            </span>
          </div>
          <h1 className="text-4xl md:text-5xl font-bold text-foreground tracking-tight mb-4">
            API Key Dashboard
          </h1>
          <p className="text-muted-foreground text-base leading-relaxed max-w-3xl">
            Manage API keys without shell commands. Create, rotate, and revoke keys with audit-safe flows.
          </p>
        </div>
        <DashboardConsole />
      </main>
    </div>
  )
}
