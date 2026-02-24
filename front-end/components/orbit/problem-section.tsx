"use client"

import Image from "next/image"
import { ScrollReveal } from "./scroll-reveal"

const problems = [
  {
    number: "01",
    title: "Memory Is Fragmented",
    description: "Vector index, relational tables, cache, embedding provider. Different contracts, different failure modes, and no single source of truth.",
    code: `vector_db.store(everything)
redis.cache(maybe_relevant)
postgres.dump(just_in_case)
config.yaml  # now with extra drama`,
  },
  {
    number: "02",
    title: "Importance Is Hand-Waved",
    description: "Hardcoded ranking weights age quickly. They do not learn from outcomes, and they definitely do not read your postmortems.",
    code: `importance = 0.9 if recent
  else (0.7 if similar
  else 0.5)
# These values came from vibes`,
  },
  {
    number: "03",
    title: "No Feedback Loop",
    description: "Most stacks cannot answer: did this memory help the response or sabotage it? Without a loop, quality plateaus.",
    code: `# What do you actually retrieve
# that helps? Nobody knows.
feedback_loop = None
improvement = 0`,
  },
  {
    number: "04",
    title: "Retention Is Guesswork",
    description: "Keep data for 30 days? 90? forever? Old context piles up and starts overriding current reality.",
    code: `redis_client.setex(
  f"recent_{user_id}",
  86400,  # because somebody picked it once
  json.dumps(messages)
)`,
  },
  {
    number: "05",
    title: "Context Budget Burn",
    description: "To be safe, teams stuff prompts with 20+ memory items. Most are irrelevant, but all of them cost tokens.",
    code: `Recent messages:  10
Vector results:   5
User history:     5
Total: 20 items + noise
# Great for latency charts, not answers`,
  },
  {
    number: "06",
    title: "Quality Drifts Down",
    description: "As data grows, personalization often regresses. Old truths compete with new behavior, and the assistant starts sounding out of date.",
    code: `Month 1: 70% satisfaction
Month 2: 69% satisfaction
Month 3: 68% satisfaction
# More data, less clarity`,
  },
]

export function ProblemSection() {
  return (
    <section id="problem" className="py-32 md:py-44">
      <div className="max-w-[1400px] mx-auto px-6 md:px-10">
        {/* Section header - Palantir style */}
        <ScrollReveal>
          <div className="flex items-center gap-3 mb-6">
            <div className="w-8 h-px bg-destructive" />
            <span className="text-destructive text-xs tracking-[0.3em] uppercase">The Problem</span>
          </div>
          <h2 className="text-3xl sm:text-4xl md:text-6xl font-bold text-foreground leading-[1] tracking-tight max-w-3xl mb-6">
            AI memory is still
            <br />
            <span className="text-muted-foreground">a three-ring circus.</span>
          </h2>
          <p className="text-muted-foreground text-base md:text-lg max-w-xl leading-relaxed mb-12">
            Building memory for an AI app still means wiring multiple data systems, inventing ranking rules, and hoping quality does not decay in month two. You spend the sprint on plumbing before your product does anything useful.
          </p>
        </ScrollReveal>

        {/* Visual: broken memory */}
        <ScrollReveal>
          <div className="relative w-full aspect-[3/1] mb-20 border border-border overflow-hidden">
            <Image
              src="/images/broken-memory.jpg"
              alt="Visualization of fragmented AI memory - disconnected data nodes and broken connections"
              fill
              className="object-cover"
            />
            <div className="absolute inset-0 bg-gradient-to-t from-background via-background/40 to-transparent" />
            <div className="absolute bottom-6 left-6 md:bottom-8 md:left-8">
              <div className="text-xs text-muted-foreground tracking-wider uppercase mb-1">Current State</div>
              <div className="text-foreground text-lg md:text-2xl font-bold">Fragmented. Noisy. Hard to tune.</div>
            </div>
          </div>
        </ScrollReveal>

        {/* Problem grid - Palantir card grid style */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-px bg-border">
          {problems.map((problem, i) => (
            <ScrollReveal key={i}>
              <div className="bg-background p-8 md:p-10 h-full flex flex-col">
                <div className="flex items-baseline gap-4 mb-4">
                  <span className="text-destructive text-xs tracking-wider">{problem.number}</span>
                  <h3 className="text-foreground font-bold text-lg">{problem.title}</h3>
                </div>
                <p className="text-muted-foreground text-sm leading-relaxed mb-6 flex-1">
                  {problem.description}
                </p>
                <div className="bg-secondary p-4 border border-border">
                  <pre className="text-xs text-muted-foreground leading-relaxed whitespace-pre-wrap font-mono">
                    {problem.code}
                  </pre>
                </div>
              </div>
            </ScrollReveal>
          ))}
        </div>
      </div>
    </section>
  )
}
