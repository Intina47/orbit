"use client"

import Image from "next/image"
import { ScrollReveal } from "./scroll-reveal"

const capabilities = [
  {
    label: "A",
    title: "Semantic Interpretation",
    description: "Orbit stores meaning, not just tokens. Queries match intent and context, not brittle keyword overlap.",
    detail: "When a user asks the same thing three different ways, Orbit can still treat it as one recurring signal.",
  },
  {
    label: "B",
    title: "Outcome-Weighted Importance",
    description: "Memory rank is adjusted by outcomes and feedback. Helpful memories move up; distracting ones cool off.",
    detail: "The system learns from production behavior instead of frozen constants tucked in a helper file.",
  },
  {
    label: "C",
    title: "Adaptive Decay",
    description: "Old memories are not deleted blindly or kept forever. Orbit decays stale context while preserving durable facts.",
    detail: "Yesterday's confusion fades when a user improves. No manual cleanup cron theater required.",
  },
  {
    label: "D",
    title: "Diversity-Aware Retrieval",
    description: "Orbit balances relevance with coverage so one long response does not crowd out profile facts and progress signals.",
    detail: "Top-k retrieval stays useful because results are ranked for utility, not just verbosity.",
  },
  {
    label: "E",
    title: "Inferred User Memory",
    description: "Orbit can write inferred memories like learning patterns and style preferences when repeated evidence exists.",
    detail: "You are not limited to raw chat logs. The system builds compact user understanding over time.",
  },
  {
    label: "F",
    title: "Transparent Provenance",
    description: "Retrieve responses include inference provenance metadata so you can see why a memory exists and what produced it.",
    detail: "When quality shifts, debugging is evidence-based, not detective fiction.",
  },
]

export function CapabilitiesSection() {
  return (
    <section className="py-32 md:py-44 bg-secondary">
      <div className="max-w-[1400px] mx-auto px-6 md:px-10">
        <ScrollReveal>
          <div className="flex items-center gap-3 mb-6">
            <div className="w-8 h-px bg-primary" />
            <span className="text-primary text-xs tracking-[0.3em] uppercase text-glow-sm">Capabilities</span>
          </div>
          <h2 className="text-3xl sm:text-4xl md:text-6xl font-bold text-foreground leading-[1] tracking-tight max-w-3xl mb-6">
            Orbit is not
            <br />
            <span className="text-muted-foreground">just a vector wrapper.</span>
          </h2>
          <p className="text-muted-foreground text-base md:text-lg max-w-xl leading-relaxed mb-12">
            It is a complete memory layer for developer products: ingestion, ranking, decay, personalization inference, and observability in one runtime.
          </p>
        </ScrollReveal>

        {/* Semantic layers visual */}
        <ScrollReveal>
          <div className="relative w-full aspect-[21/9] mb-20 border border-border overflow-hidden">
            <Image
              src="/images/semantic-layers.jpg"
              alt="Layered semantic architecture - multiple processing planes for encoding, scoring, and decay"
              fill
              className="object-cover"
            />
            <div className="absolute inset-0 bg-gradient-to-r from-background/80 via-transparent to-background/80" />
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="text-center">
                <div className="text-xs text-muted-foreground tracking-[0.3em] uppercase mb-2">Semantic Architecture</div>
                <div className="text-foreground text-xl md:text-3xl font-bold">Six layers. One contract.</div>
              </div>
            </div>
          </div>
        </ScrollReveal>

        {/* Palantir-style labeled grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-px bg-border">
          {capabilities.map((cap, i) => (
            <ScrollReveal key={i}>
              <div className="bg-background p-8 md:p-10 h-full group hover:bg-background/80 transition-colors">
                <div className="flex items-center gap-4 mb-6">
                  <span className="text-primary text-xs tracking-wider text-glow-sm">{'--'}{cap.label}</span>
                  <div className="h-px flex-1 bg-border" />
                </div>
                <h3 className="text-foreground font-bold text-xl md:text-2xl mb-4">{cap.title}</h3>
                <p className="text-muted-foreground text-sm leading-relaxed mb-4">
                  {cap.description}
                </p>
                <p className="text-muted-foreground/70 text-xs leading-relaxed">
                  {cap.detail}
                </p>
              </div>
            </ScrollReveal>
          ))}
        </div>
      </div>
    </section>
  )
}
