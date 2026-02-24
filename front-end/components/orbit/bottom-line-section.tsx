"use client"

import { ScrollReveal } from "./scroll-reveal"

export function BottomLineSection() {
  return (
    <section className="py-32 md:py-44 bg-secondary">
      <div className="max-w-[1400px] mx-auto px-6 md:px-10">
        <ScrollReveal>
          <div className="flex items-center gap-3 mb-6">
            <div className="w-8 h-px bg-primary" />
            <span className="text-primary text-xs tracking-[0.3em] uppercase text-glow-sm">The Bottom Line</span>
          </div>
        </ScrollReveal>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-px bg-border">
          <ScrollReveal>
            <div className="bg-background p-10 md:p-16 h-full">
              <div className="text-destructive text-xs tracking-wider font-bold mb-6">WITHOUT ORBIT</div>
              <h3 className="text-foreground font-bold text-2xl md:text-4xl leading-[1.1] mb-6">
                Most effort goes to
                <br />
                memory maintenance.
              </h3>
              <p className="text-muted-foreground text-sm leading-relaxed mb-8">
                Teams spend serious time babysitting relevance, retention, and ranking. The product moves, but slower than it should.
              </p>
              <div className="border border-border p-6">
                <div className="text-muted-foreground text-sm mb-2">For the same engineering effort:</div>
                <div className="text-foreground text-xl font-bold">One assistant that is hard to tune</div>
                <div className="text-muted-foreground text-sm mt-1">and gets noisier over time</div>
              </div>
            </div>
          </ScrollReveal>

          <ScrollReveal>
            <div className="bg-background p-10 md:p-16 h-full">
              <div className="text-primary text-xs tracking-wider font-bold mb-6 text-glow-sm">WITH ORBIT</div>
              <h3 className="text-foreground font-bold text-2xl md:text-4xl leading-[1.1] mb-6">
                Most effort goes to
                <br />
                user experience.
              </h3>
              <p className="text-muted-foreground text-sm leading-relaxed mb-8">
                Memory stays focused, adapts with feedback, and remains observable. Engineers spend time on product decisions instead of memory triage.
              </p>
              <div className="border border-primary p-6">
                <div className="text-primary text-sm mb-2 text-glow-sm">For the same engineering effort:</div>
                <div className="text-primary text-xl font-bold text-glow">A portfolio of assistants that actually improve</div>
                <div className="text-primary text-sm mt-1 text-glow-sm">without custom memory rewrites every quarter</div>
              </div>
            </div>
          </ScrollReveal>
        </div>

        <ScrollReveal>
          <div className="mt-20 text-center">
            <p className="text-foreground text-2xl md:text-4xl font-bold mb-2">
              Memory should be a product advantage, not your side quest.
            </p>
          </div>
        </ScrollReveal>
      </div>
    </section>
  )
}
