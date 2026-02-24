"use client"

import { ScrollReveal } from "./scroll-reveal"

const timeline = [
  {
    period: "Week 1",
    without: {
      quote: "Let me wire vector search, SQL, and cache first...",
      time: "Most of the week goes to memory plumbing and ranking hacks.",
      result: "Assistant launches, but personalization feels shallow.",
    },
    with: {
      quote: "Let me integrate Orbit and ship the product flow.",
      time: "Core memory loop is up quickly with ingest, retrieve, and feedback.",
      result: "Assistant launches with focused, user-aware context.",
    },
  },
  {
    period: "Month 1",
    without: {
      quote: "Why is the model suddenly quoting stale context?",
      time: "Team spends cycles tuning decay and fighting noisy retrieval.",
      result: "Progress is possible, but slow and expensive.",
    },
    with: {
      quote: "Retrieval quality trend is up. Nice.",
      time: "Team focuses on product features while memory keeps learning.",
      result: "Users notice the assistant adapting to their progress.",
    },
  },
  {
    period: "Month 3",
    without: {
      quote: "We need a memory rewrite before the next release.",
      time: "Scaling pressure lands on custom infra and brittle heuristics.",
      result: "Roadmap slows because memory stack became its own project.",
    },
    with: {
      quote: "Memory is boring now. Exactly what we wanted.",
      time: "Runtime stays stable as traffic grows.",
      result: "Team keeps shipping while personalization gets sharper.",
    },
  },
]

export function TimelineSection() {
  return (
    <section className="py-32 md:py-44">
      <div className="max-w-[1400px] mx-auto px-6 md:px-10">
        <ScrollReveal>
          <div className="flex items-center gap-3 mb-6">
            <div className="w-8 h-px bg-primary" />
            <span className="text-primary text-xs tracking-[0.3em] uppercase text-glow-sm">Developer Journey</span>
          </div>
          <h2 className="text-3xl sm:text-4xl md:text-6xl font-bold text-foreground leading-[1] tracking-tight max-w-3xl mb-20">
            Same team.
            <br />
            Very different quarter.
          </h2>
        </ScrollReveal>

        <div className="space-y-0">
          {timeline.map((phase, i) => (
            <ScrollReveal key={i}>
              <div className={`grid grid-cols-1 lg:grid-cols-[200px_1fr_1fr] gap-0 ${i < timeline.length - 1 ? "border-b border-border" : ""}`}>
                {/* Period label */}
                <div className="py-10 lg:pr-10 lg:border-r border-border">
                  <span className="text-foreground font-bold text-2xl md:text-3xl">{phase.period}</span>
                </div>

                {/* Without */}
                <div className="py-10 lg:px-10 lg:border-r border-border">
                  <div className="text-destructive text-xs tracking-wider font-bold mb-4">WITHOUT ORBIT</div>
                  <p className="text-foreground text-sm font-bold mb-2">{'"'}{phase.without.quote}{'"'}</p>
                  <p className="text-muted-foreground text-sm mb-4">{phase.without.time}</p>
                  <p className="text-muted-foreground text-xs border-l-2 border-destructive pl-4">{phase.without.result}</p>
                </div>

                {/* With */}
                <div className="py-10 lg:px-10">
                  <div className="text-primary text-xs tracking-wider font-bold mb-4 text-glow-sm">WITH ORBIT</div>
                  <p className="text-foreground text-sm font-bold mb-2">{'"'}{phase.with.quote}{'"'}</p>
                  <p className="text-muted-foreground text-sm mb-4">{phase.with.time}</p>
                  <p className="text-primary text-xs border-l-2 border-primary pl-4 text-glow-sm">{phase.with.result}</p>
                </div>
              </div>
            </ScrollReveal>
          ))}
        </div>
      </div>
    </section>
  )
}
