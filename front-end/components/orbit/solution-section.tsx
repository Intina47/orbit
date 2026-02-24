"use client"

import { useState } from "react"
import Image from "next/image"
import { ScrollReveal } from "./scroll-reveal"

const withoutOrbitCode = `from fastapi import FastAPI
from sqlalchemy import create_engine
import pinecone
from redis import Redis
from openai import OpenAI

app = FastAPI()
db = create_engine("postgresql://...")
pinecone.init(api_key="pk-...")
redis_client = Redis(host="localhost", port=6379)
openai_client = OpenAI(api_key="sk-...")

class MemoryManager:
    def __init__(self):
        self.pinecone_index = pinecone.Index("coding-chatbot")
        self.db = db
        self.redis = redis_client

    def store_interaction(self, user_id, message, response):
        embedding = openai_client.Embedding.create(
            input=message,
            model="text-embedding-3-small"
        )["data"][0]["embedding"]

        self.pinecone_index.upsert(
            vectors=[(f"msg_{user_id}_{timestamp}",
                embedding, {"user_id": user_id})]
        )

        with self.db.connect() as conn:
            conn.execute("INSERT INTO interactions ...")

        redis_client.setex(
            f"recent_{user_id}", 86400,
            json.dumps([message, response])
        )

    def retrieve_context(self, user_id, message, limit=5):
        cached = redis_client.get(f"recent_{user_id}")
        embedding = openai_client.Embedding.create(...)
        vector_results = self.pinecone_index.query(...)

        with self.db.connect() as conn:
            db_results = conn.execute(...)

        return self._manually_rank_context(
            vector_results, db_results, cached
        )

    def _manually_rank_context(self, vectors, db, recent):
        # Hardcoded. Never learns.
        ranked = []
        for item in recent:
            ranked.append({"importance": 0.9})
        for result in vectors:
            ranked.append({"importance": 0.7})
        for result in db:
            ranked.append({"importance": 0.5})
        return sorted(ranked, key=lambda x: x["importance"])[:5]`

const withOrbitCode = `from fastapi import FastAPI
from orbit import MemoryEngine
from openai import OpenAI

app = FastAPI()
orbit = MemoryEngine(api_key="orbit_pk_...")
openai_client = OpenAI(api_key="sk-...")

@app.post("/chat")
async def chat(user_id: str, message: str):
    # Store signal
    orbit.ingest(
        content=message,
        event_type="user_question",
        entity_id=user_id
    )

    # Retrieve clean context
    memories = orbit.retrieve(
        query=f"Help with: {message}",
        entity_id=user_id,
        limit=5
    )

    # Call LLM
    response = openai_client.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": format(memories)},
            {"role": "user", "content": message}
        ]
    )

    # Store assistant output
    orbit.ingest(
        content=response.choices[0].message.content,
        event_type="assistant_response",
        entity_id=user_id
    )

    return {"response": response.choices[0].message.content}

@app.post("/feedback")
async def feedback(user_id: str, memory_id: str, helpful: bool):
    orbit.feedback(
        memory_id=memory_id,
        helpful=helpful,
        outcome_value=1.0 if helpful else -1.0
    )
    return {"recorded": True}`

export function SolutionSection() {
  const [activeTab, setActiveTab] = useState<"without" | "with">("without")

  return (
    <section id="how-it-works" className="py-32 md:py-44">
      <div className="max-w-[1400px] mx-auto px-6 md:px-10">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 lg:gap-20">
          {/* Left: text content */}
          <div>
            <ScrollReveal>
              <div className="flex items-center gap-3 mb-6">
                <div className="w-8 h-px bg-primary" />
                <span className="text-primary text-xs tracking-[0.3em] uppercase text-glow-sm">The Solution</span>
              </div>
              <h2 className="text-3xl sm:text-4xl md:text-6xl font-bold text-foreground leading-[1] tracking-tight mb-6">
                Memory plumbing
                <br />
                to memory product.
              </h2>
              <p className="text-muted-foreground text-base md:text-lg leading-relaxed mb-8 max-w-md">
                Orbit replaces a stitched-together memory stack with one contract. You send events, fetch context, and close the loop with feedback. Ranking, decay, inference, and retrieval tuning happen behind the API.
              </p>
            </ScrollReveal>

            {/* Orbit engine visual */}
            <ScrollReveal>
              <div className="relative w-full aspect-[4/3] mb-10 border border-border overflow-hidden">
                <Image
                  src="/images/orbit-engine.jpg"
                  alt="Orbit unified memory engine visualization - data streams converging into a central intelligence core"
                  fill
                  className="object-cover"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-background via-transparent to-transparent" />
                <div className="absolute bottom-4 left-4 right-4 flex items-end justify-between">
                  <div>
                    <div className="text-xs text-muted-foreground tracking-wider uppercase">Architecture</div>
                    <div className="text-foreground text-sm font-bold">One engine. Fewer moving parts.</div>
                  </div>
                  <div className="text-primary text-glow-sm text-xs">orbit.core</div>
                </div>
              </div>
            </ScrollReveal>

            <ScrollReveal>
              {/* Key differences */}
              <div className="space-y-8">
                {[
                  {
                    label: "Build Complexity",
                    without: "300+ lines of infra and manual ranking",
                    with: "A small SDK surface and deterministic flow",
                  },
                  {
                    label: "Operations",
                    without: "Tune multiple systems and retention rules by hand",
                    with: "Run one runtime, monitor one memory API",
                  },
                  {
                    label: "Retrieval Quality",
                    without: "Similarity-heavy results and noisy context packs",
                    with: "Outcome-aware ranking with cleaner top-k",
                  },
                  {
                    label: "Team Focus",
                    without: "Infra firefighting dominates roadmap time",
                    with: "Roadmap stays focused on user experience",
                  },
                ].map((diff, i) => (
                  <div key={i} className="border-l-2 border-border pl-6">
                    <div className="text-foreground font-bold text-sm mb-2">{diff.label}</div>
                    <div className="flex flex-col gap-2">
                      <div className="flex items-start gap-2">
                        <span className="text-destructive text-xs shrink-0 mt-0.5">{'[OLD]'}</span>
                        <span className="text-muted-foreground text-sm">{diff.without}</span>
                      </div>
                      <div className="flex items-start gap-2">
                        <span className="text-primary text-xs shrink-0 mt-0.5 text-glow-sm">{'[NEW]'}</span>
                        <span className="text-foreground text-sm">{diff.with}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </ScrollReveal>
          </div>

          {/* Right: code comparison - Stripe style */}
          <div className="lg:sticky lg:top-10 lg:self-start">
            <ScrollReveal>
              <div className="border border-border">
                {/* Tab bar */}
                <div className="flex border-b border-border">
                  <button
                    onClick={() => setActiveTab("without")}
                    className={`flex-1 px-6 py-3 text-xs tracking-wider font-bold transition-colors ${
                      activeTab === "without"
                        ? "text-destructive border-b-2 border-destructive bg-secondary"
                        : "text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    WITHOUT ORBIT
                    <span className="ml-2 text-muted-foreground">300+ lines</span>
                  </button>
                  <button
                    onClick={() => setActiveTab("with")}
                    className={`flex-1 px-6 py-3 text-xs tracking-wider font-bold transition-colors ${
                      activeTab === "with"
                        ? "text-primary border-b-2 border-primary bg-secondary"
                        : "text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    WITH ORBIT
                    <span className="ml-2 text-muted-foreground">20 lines</span>
                  </button>
                </div>

                {/* Code block */}
                <div className="p-6 max-h-[600px] overflow-y-auto">
                  <pre className="text-xs leading-relaxed whitespace-pre-wrap">
                    <code className={activeTab === "without" ? "text-muted-foreground" : "text-foreground"}>
                      {activeTab === "without" ? withoutOrbitCode : withOrbitCode}
                    </code>
                  </pre>
                </div>

                {/* Bottom status */}
                <div className="border-t border-border px-6 py-3 flex items-center justify-between text-xs">
                  {activeTab === "without" ? (
                    <>
                      <span className="text-destructive">Too many systems. No learning loop.</span>
                      <span className="text-muted-foreground">Python</span>
                    </>
                  ) : (
                    <>
                      <span className="text-primary text-glow-sm">One memory layer. Adaptive by default.</span>
                      <span className="text-muted-foreground">Python</span>
                    </>
                  )}
                </div>
              </div>
            </ScrollReveal>
          </div>
        </div>
      </div>
    </section>
  )
}
