"use client"

import { useState, useEffect } from "react"
import Image from "next/image"
import Link from "next/link"
import { BlinkingCursor } from "./blinking-cursor"

export function Hero() {
  const [showSubtext, setShowSubtext] = useState(false)
  const [showCTA, setShowCTA] = useState(false)

  useEffect(() => {
    const t1 = setTimeout(() => setShowSubtext(true), 600)
    const t2 = setTimeout(() => setShowCTA(true), 1200)
    return () => {
      clearTimeout(t1)
      clearTimeout(t2)
    }
  }, [])

  return (
    <section className="relative min-h-screen flex flex-col overflow-hidden">
      {/* Background image */}
      <div className="absolute inset-0 pointer-events-none">
        <Image
          src="/images/hero-memory-network.jpg"
          alt=""
          fill
          className="object-cover opacity-20"
          priority
        />
        <div className="absolute inset-0 bg-gradient-to-b from-background/60 via-background/80 to-background" />
      </div>
      {/* Nav */}
      <nav className="relative z-10 w-full border-b border-border">
        <div className="max-w-[1400px] mx-auto px-6 md:px-10 py-5 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-2 h-2 bg-primary" />
            <span className="text-foreground font-bold tracking-widest text-sm">ORBIT</span>
          </div>
          <div className="hidden md:flex items-center gap-8 text-xs tracking-wider text-muted-foreground">
            <Link href="/docs" className="hover:text-foreground transition-colors">DOCS</Link>
            <a href="#problem" className="hover:text-foreground transition-colors">PROBLEM</a>
            <a href="#how-it-works" className="hover:text-foreground transition-colors">HOW IT WORKS</a>
            <a href="#comparison" className="hover:text-foreground transition-colors">COMPARISON</a>
            <a href="#metrics" className="hover:text-foreground transition-colors">METRICS</a>
          </div>
          <a
            href="#cta"
            className="border border-foreground px-5 py-2 text-foreground text-xs tracking-wider hover:bg-foreground hover:text-background transition-all duration-200"
          >
            START NOW
          </a>
        </div>
      </nav>

      {/* Hero Content */}
      <div className="relative z-10 flex-1 flex items-center">
        <div className="max-w-[1400px] mx-auto px-6 md:px-10 py-20 md:py-0 w-full">
          <div className="max-w-4xl">
            {/* Label */}
            <div className="flex items-center gap-3 mb-8">
              <div className="w-8 h-px bg-primary" />
              <span className="text-primary text-xs tracking-[0.3em] uppercase text-glow-sm">Memory Infrastructure for Developer Apps</span>
            </div>

            {/* Main heading */}
            <h1 className="text-4xl sm:text-5xl md:text-7xl lg:text-8xl font-bold text-foreground leading-[0.95] tracking-tight mb-8">
              Your AI app
              <br />
              remembers the chat,
              <br />
              <span className="text-primary text-glow">forgets the person.</span>
              <br />
              Orbit fixes that.
            </h1>

            {/* Subtext */}
            <div className={`transition-all duration-700 ${showSubtext ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4"}`}>
              <p className="text-muted-foreground text-base md:text-lg leading-relaxed max-w-xl mb-12">
                Orbit is memory for chatbots, copilots, and agent products.
                Ingest events, retrieve sharp context, send feedback.
                Orbit learns what matters, trims the noise, and keeps your prompt on speaking terms with the context window.
              </p>
            </div>

            {/* CTAs */}
            <div className={`transition-all duration-700 delay-300 ${showCTA ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4"}`}>
              <div className="flex flex-col sm:flex-row gap-4">
                <a
                  href="#cta"
                  className="bg-primary text-primary-foreground px-8 py-4 font-bold tracking-wider text-sm hover:bg-accent transition-all duration-200 text-center"
                >
                  BUILD WITH ORBIT
                </a>
                <a
                  href="/docs"
                  className="border border-border px-8 py-4 text-foreground font-bold tracking-wider text-sm hover:border-foreground transition-all duration-200 text-center"
                >
                  READ DOCS
                </a>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Bottom stats bar - Palantir style */}
      <div className="relative z-10 border-t border-border bg-background/80 backdrop-blur-sm">
        <div className="max-w-[1400px] mx-auto px-6 md:px-10">
          <div className="grid grid-cols-2 md:grid-cols-4">
            {[
              { value: "1 SDK", label: "Ingest, retrieve, feedback" },
              { value: "5 results", label: "Default context payload" },
              { value: "Adaptive", label: "Learns from outcomes" },
              { value: "Postgres", label: "Production runtime first" },
            ].map((stat, i) => (
              <div key={i} className={`py-6 ${i < 3 ? "border-r border-border" : ""} ${i > 0 ? "pl-6 md:pl-8" : ""}`}>
                <div className="text-primary text-2xl md:text-3xl font-bold text-glow-sm">{stat.value}</div>
                <div className="text-muted-foreground text-xs tracking-wider mt-1 uppercase">{stat.label}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}
