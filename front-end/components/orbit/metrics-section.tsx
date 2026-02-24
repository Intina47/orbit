"use client"

import { useEffect, useRef, useState } from "react"
import Image from "next/image"
import { ScrollReveal } from "./scroll-reveal"

interface MetricRow {
  label: string
  without: string
  with: string
  highlight?: boolean
}

const metrics: MetricRow[] = [
  { label: "Integration Time", without: "3+ days", with: "~20 minutes" },
  { label: "Memory Infra LOC", without: "300+", with: "20-40" },
  { label: "Datastores to Run", without: "3+", with: "1" },
  { label: "Manual Tuning", without: "Weekly", with: "Rare" },
  { label: "Context Payload", without: "15-25 items", with: "5-8 items", highlight: true },
  { label: "Month-3 Quality Trend", without: "Drifts down", with: "Improves with feedback", highlight: true },
  { label: "Prompt Token Waste", without: "High", with: "Lower" },
  { label: "Developer Hours/Month", without: "20+", with: "<2" },
  { label: "Learning Loop", without: "Manual", with: "Built-in", highlight: true },
  { label: "Retrieval Debugging", without: "Guessing", with: "Provenance metadata" },
  { label: "Rate Limits + Quotas", without: "Custom work", with: "Runtime defaults" },
  { label: "Production DB Path", without: "Hand-rolled", with: "Postgres-first" },
]

function AnimatedBar({ percent, delay }: { percent: number; delay: number }) {
  const ref = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(0)
  const [isVisible, setIsVisible] = useState(false)

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsVisible(true)
          observer.disconnect()
        }
      },
      { threshold: 0.5 }
    )
    if (ref.current) observer.observe(ref.current)
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    if (isVisible) {
      const timer = setTimeout(() => setWidth(percent), delay)
      return () => clearTimeout(timer)
    }
  }, [isVisible, percent, delay])

  return (
    <div ref={ref} className="h-1 bg-secondary flex-1">
      <div
        className="h-full bg-primary transition-all duration-1000 ease-out"
        style={{ width: `${width}%` }}
      />
    </div>
  )
}

export function MetricsSection() {
  return (
    <section id="metrics" className="py-32 md:py-44">
      <div className="max-w-[1400px] mx-auto px-6 md:px-10">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 lg:gap-20">
          {/* Left: headline + summary metrics */}
          <div>
            <ScrollReveal>
              <div className="flex items-center gap-3 mb-6">
                <div className="w-8 h-px bg-primary" />
                <span className="text-primary text-xs tracking-[0.3em] uppercase text-glow-sm">After 90 Days</span>
              </div>
              <h2 className="text-3xl sm:text-4xl md:text-6xl font-bold text-foreground leading-[1] tracking-tight mb-6">
                Memory quality
                <br />
                compounds.
              </h2>
              <p className="text-muted-foreground text-base md:text-lg leading-relaxed max-w-md mb-10">
                In production, memory either gets noisier or gets smarter. Orbit is built so retrieval quality improves with feedback instead of degrading under data growth.
              </p>
            </ScrollReveal>

            {/* Growth trajectory visual */}
            <ScrollReveal>
              <div className="relative w-full aspect-[16/9] mb-16 border border-border overflow-hidden">
                <Image
                  src="/images/growth-trajectory.jpg"
                  alt="Quality trajectory comparison - Orbit improving upward vs traditional declining downward over time"
                  fill
                  className="object-cover"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-background via-transparent to-background/40" />
                <div className="absolute bottom-4 left-4 right-4 flex items-end justify-between">
                  <div className="flex items-center gap-4">
                    <div className="flex items-center gap-2">
                      <div className="w-3 h-px bg-primary" />
                      <span className="text-primary text-xs text-glow-sm">Orbit</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="w-3 h-px bg-destructive" />
                      <span className="text-destructive text-xs">Traditional</span>
                    </div>
                  </div>
                  <span className="text-muted-foreground text-xs">30-90 day behavior</span>
                </div>
              </div>
            </ScrollReveal>

            {/* Big stat cards */}
            <ScrollReveal>
              <div className="grid grid-cols-2 gap-px bg-border">
                {[
                  { value: "5", label: "Default retrieved items", sub: "clean top-k context" },
                  { value: "1", label: "Core memory API", sub: "ingest, retrieve, feedback" },
                  { value: "Adaptive", label: "Ranking and decay", sub: "learn from outcomes" },
                  { value: "Traceable", label: "Inference provenance", sub: "why this memory exists" },
                ].map((stat, i) => (
                  <div key={i} className="bg-background p-6">
                    <div className="text-primary text-3xl md:text-4xl font-bold text-glow-sm mb-1">{stat.value}</div>
                    <div className="text-foreground text-sm mb-1">{stat.label}</div>
                    <div className="text-muted-foreground text-xs">{stat.sub}</div>
                  </div>
                ))}
              </div>
            </ScrollReveal>
          </div>

          {/* Right: comparison table */}
          <div>
            <ScrollReveal>
              <div className="border border-border">
                {/* Table header */}
                <div className="grid grid-cols-3 border-b border-border">
                  <div className="px-6 py-4 text-xs text-muted-foreground tracking-wider">METRIC</div>
                  <div className="px-6 py-4 text-xs text-muted-foreground tracking-wider border-l border-border">WITHOUT</div>
                  <div className="px-6 py-4 text-xs text-primary tracking-wider border-l border-border text-glow-sm">WITH ORBIT</div>
                </div>

                {/* Table rows */}
                {metrics.map((row, i) => (
                  <div
                    key={i}
                    className={`grid grid-cols-3 border-b border-border last:border-b-0 ${
                      row.highlight ? "bg-secondary/50" : ""
                    }`}
                  >
                    <div className="px-6 py-3 text-foreground text-sm">{row.label}</div>
                    <div className="px-6 py-3 text-muted-foreground text-sm border-l border-border">{row.without}</div>
                    <div className="px-6 py-3 text-primary text-sm border-l border-border text-glow-sm">{row.with}</div>
                  </div>
                ))}
              </div>
            </ScrollReveal>
          </div>
        </div>
      </div>
    </section>
  )
}
