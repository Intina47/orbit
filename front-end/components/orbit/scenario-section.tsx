"use client"

import { useState } from "react"
import { ScrollReveal } from "./scroll-reveal"

const scenarios = [
  {
    id: "day1",
    label: "Day 1",
    title: "Alice asks: 'What is a for loop?'",
    without: {
      steps: [
        "Retrieves recent thread + semantic hits + stale profile notes",
        "15+ memory chunks land in prompt context",
        "Several chunks are old or generic",
        "Model spends tokens sorting noise from signal",
        "Answer sounds correct, but not truly personalized",
      ],
      result: "User: 'Helpful enough, I guess.'",
      developer: "Developer: no clue which memories helped and which just burned tokens.",
    },
    with: {
      steps: [
        "'Alice is a beginner'",
        "'Alice struggles with function syntax'",
        "'Alice prefers short explanations'",
        "'Alice responds well to analogies'",
        "'Alice has not covered scope yet'",
      ],
      result: "User: 'Perfect. That finally clicked.'",
      developer: "Orbit records the outcome and reinforces the winning pattern.",
    },
  },
  {
    id: "day30",
    label: "Day 30",
    title: "Alice improves and asks: 'How should I structure a larger project?'",
    without: {
      steps: [
        "Old beginner memories still rank near the top",
        "Recent growth signals compete with month-old baseline data",
        "Ranking logic still uses Day 1 assumptions",
        "Assistant responds as if Alice never progressed",
        "User: 'Why are we still on baby steps?'",
      ],
      result: "Trust drops because memory feels out of date.",
      developer: "Developer starts hand-patching ranking rules in production.",
    },
    with: {
      steps: [
        "'Alice completed 10 lessons'",
        "'Alice now handles functions, loops, and classes'",
        "'Alice is improving on OOP structure'",
        "'Alice prefers practical project examples'",
        "'Recent questions are intermediate level'",
      ],
      result: "User: 'Yes. This matches where I am now.'",
      developer: "Decay downweights stale baseline data automatically.",
    },
  },
  {
    id: "month3",
    label: "Month 3",
    title: "1,000 users later. Reality check.",
    without: {
      steps: [
        "Memory corpus grows fast, ranking quality drifts",
        "Latency climbs as context payloads get bigger",
        "Prompt tokens are spent on low-value history",
        "User satisfaction slips and support tickets climb",
        "Team spends roadmap time tuning memory internals",
      ],
      result: "System works, but running it feels like a second product.",
      developer: "Roadmap conversation becomes: fix memory stack or ship features?",
    },
    with: {
      steps: [
        "Important memories stay hot, stale noise decays",
        "Retrieval remains focused at small top-k",
        "Context payload stays lean",
        "User quality trend improves with feedback",
        "Team keeps shipping product features",
      ],
      result: "System gets sharper as usage grows.",
      developer: "Memory layer stops being the loudest thing in sprint planning.",
    },
  },
]

export function ScenarioSection() {
  const [activeScenario, setActiveScenario] = useState(0)
  const scenario = scenarios[activeScenario]

  return (
    <section id="comparison" className="py-32 md:py-44 bg-secondary">
      <div className="max-w-[1400px] mx-auto px-6 md:px-10">
        <ScrollReveal>
          <div className="flex items-center gap-3 mb-6">
            <div className="w-8 h-px bg-primary" />
            <span className="text-primary text-xs tracking-[0.3em] uppercase text-glow-sm">Real-World Scenario</span>
          </div>
          <h2 className="text-3xl sm:text-4xl md:text-6xl font-bold text-foreground leading-[1] tracking-tight max-w-4xl mb-4">
            Coding tutor chatbot.
            <br />
            <span className="text-muted-foreground">Same app, two memory systems.</span>
          </h2>
          <p className="text-muted-foreground text-base md:text-lg max-w-xl leading-relaxed mb-16">
            This is where memory either helps your product grow up or keeps it stuck rerunning old conversations. Compare outcomes across day one, day thirty, and real production load.
          </p>
        </ScrollReveal>

        {/* Timeline tabs */}
        <ScrollReveal>
          <div className="flex gap-0 mb-12 border-b border-border">
            {scenarios.map((s, i) => (
              <button
                key={s.id}
                onClick={() => setActiveScenario(i)}
                className={`px-6 md:px-10 py-4 text-sm tracking-wider font-bold transition-all ${
                  activeScenario === i
                    ? "text-primary border-b-2 border-primary"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                {s.label}
              </button>
            ))}
          </div>
        </ScrollReveal>

        {/* Scenario content */}
        <ScrollReveal>
          <div className="mb-8">
            <h3 className="text-foreground font-bold text-xl md:text-2xl mb-2">{scenario.title}</h3>
          </div>
        </ScrollReveal>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-px bg-border">
          {/* Without Orbit */}
          <ScrollReveal>
            <div className="bg-background p-8 md:p-10 h-full">
              <div className="flex items-center gap-3 mb-8">
                <div className="w-3 h-3 border-2 border-destructive" />
                <span className="text-destructive font-bold text-sm tracking-wider">WITHOUT ORBIT</span>
              </div>

              <div className="space-y-4 mb-8">
                {scenario.without.steps.map((step, i) => (
                  <div key={i} className="flex items-start gap-3">
                    <span className="text-muted-foreground text-xs mt-1 shrink-0">{String(i + 1).padStart(2, "0")}</span>
                    <span className="text-muted-foreground text-sm leading-relaxed">{step}</span>
                  </div>
                ))}
              </div>

              <div className="border-t border-border pt-6 space-y-3">
                <div className="flex items-start gap-2">
                  <span className="text-destructive text-xs shrink-0">RESULT</span>
                  <span className="text-foreground text-sm">{scenario.without.result}</span>
                </div>
                <div className="flex items-start gap-2">
                  <span className="text-muted-foreground text-xs shrink-0">DEV</span>
                  <span className="text-muted-foreground text-sm">{scenario.without.developer}</span>
                </div>
              </div>
            </div>
          </ScrollReveal>

          {/* With Orbit */}
          <ScrollReveal>
            <div className="bg-background p-8 md:p-10 h-full">
              <div className="flex items-center gap-3 mb-8">
                <div className="w-3 h-3 bg-primary" />
                <span className="text-primary font-bold text-sm tracking-wider text-glow-sm">WITH ORBIT</span>
              </div>

              <div className="space-y-4 mb-8">
                {scenario.with.steps.map((step, i) => (
                  <div key={i} className="flex items-start gap-3">
                    <span className="text-primary text-xs mt-1 shrink-0 text-glow-sm">{String(i + 1).padStart(2, "0")}</span>
                    <span className="text-foreground text-sm leading-relaxed">{step}</span>
                  </div>
                ))}
              </div>

              <div className="border-t border-border pt-6 space-y-3">
                <div className="flex items-start gap-2">
                  <span className="text-primary text-xs shrink-0 text-glow-sm">RESULT</span>
                  <span className="text-foreground text-sm">{scenario.with.result}</span>
                </div>
                <div className="flex items-start gap-2">
                  <span className="text-primary text-xs shrink-0">DEV</span>
                  <span className="text-primary text-sm text-glow-sm">{scenario.with.developer}</span>
                </div>
              </div>
            </div>
          </ScrollReveal>
        </div>
      </div>
    </section>
  )
}
