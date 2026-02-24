"use client"

import { ScrollReveal } from "./scroll-reveal"
import { BlinkingCursor } from "./blinking-cursor"

export function CTA() {
  return (
    <section id="cta" className="py-32 md:py-44">
      <div className="max-w-[1400px] mx-auto px-6 md:px-10">
        <div className="max-w-3xl mx-auto text-center">
          <ScrollReveal>
            <div className="flex items-center justify-center gap-3 mb-8">
              <div className="w-8 h-px bg-primary" />
              <span className="text-primary text-xs tracking-[0.3em] uppercase text-glow-sm">Get Started</span>
              <div className="w-8 h-px bg-primary" />
            </div>

            <h2 className="text-3xl sm:text-4xl md:text-6xl lg:text-7xl font-bold text-foreground leading-[0.95] tracking-tight mb-6">
              Ready to ship an AI app
              <br />
              that remembers people,
              <br />
              not just prompts?
              <BlinkingCursor className="ml-1" />
            </h2>

            <p className="text-muted-foreground text-base md:text-lg leading-relaxed mb-12 max-w-lg mx-auto">
              Orbit handles memory infrastructure so your team can focus on product behavior, response quality, and user outcomes.
            </p>

            <div className="flex flex-col sm:flex-row gap-4 justify-center mb-8">
              <a
                href="#"
                className="bg-primary text-primary-foreground px-10 py-4 font-bold tracking-wider text-sm hover:bg-accent transition-all duration-200"
              >
                START BUILDING
              </a>
              <a
                href="#"
                className="border border-foreground px-10 py-4 text-foreground font-bold tracking-wider text-sm hover:bg-foreground hover:text-background transition-all duration-200"
              >
                TALK TO US
              </a>
            </div>

            <div className="text-xs text-muted-foreground">
              or run: <span className="text-primary text-glow-sm">pip install orbit-memory</span>
            </div>
          </ScrollReveal>
        </div>
      </div>
    </section>
  )
}
