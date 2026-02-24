import { Hero } from "@/components/orbit/hero"
import { ProblemSection } from "@/components/orbit/problem-section"
import { SolutionSection } from "@/components/orbit/solution-section"
import { ScenarioSection } from "@/components/orbit/scenario-section"
import { CapabilitiesSection } from "@/components/orbit/capabilities-section"
import { MetricsSection } from "@/components/orbit/metrics-section"
import { TimelineSection } from "@/components/orbit/timeline-section"
import { BottomLineSection } from "@/components/orbit/bottom-line-section"
import { CTA } from "@/components/orbit/cta"
import { Footer } from "@/components/orbit/footer"

export default function OrbitLanding() {
  return (
    <main className="min-h-screen bg-background text-foreground">
      {/* Full-screen hero with nav, headline, and stats bar */}
      <Hero />

      {/* The Problem: 6-card grid showing broken AI memory */}
      <ProblemSection />

      {/* The Solution: side-by-side code comparison (300 lines vs 20) */}
      <SolutionSection />

      {/* Real-world scenario: Day 1, Day 30, Month 3 tabbed comparison */}
      <ScenarioSection />

      {/* Capabilities: 6-card Palantir-style labeled grid */}
      <CapabilitiesSection />

      {/* Metrics: full comparison table with animated stats */}
      <MetricsSection />

      {/* Developer journey timeline */}
      <TimelineSection />

      {/* The Bottom Line: without vs with final summary */}
      <BottomLineSection />

      {/* CTA */}
      <CTA />

      {/* Footer */}
      <Footer />
    </main>
  )
}
