"use client"

import { useMemo, useState } from "react"

type AiTarget = "chatgpt" | "claude" | "cursor"
type SetupRoute = "cloud" | "self_hosted"
type LanguageTarget = "nodejs" | "python" | "go" | "typescript"
type AppTarget = "chatbot" | "agent" | "saas_api" | "support_bot"

const aiTargets: Array<{ id: AiTarget; label: string }> = [
  { id: "chatgpt", label: "ChatGPT" },
  { id: "claude", label: "Claude" },
  { id: "cursor", label: "Cursor" },
]

const languageTargets: Array<{ id: LanguageTarget; label: string }> = [
  { id: "nodejs", label: "Node.js" },
  { id: "typescript", label: "TypeScript" },
  { id: "python", label: "Python" },
  { id: "go", label: "Go" },
]

const appTargets: Array<{ id: AppTarget; label: string }> = [
  { id: "chatbot", label: "Chatbot" },
  { id: "agent", label: "Agent Runtime" },
  { id: "saas_api", label: "SaaS API" },
  { id: "support_bot", label: "Support Assistant" },
]

const orbitWebsiteUrl = "https://orbit-memory.vercel.app"
const orbitDocsUrl = "https://orbit-memory.vercel.app/docs"
const orbitGithubRepoUrl = "https://github.com/intina47/orbit"
const orbitGithubExamplesBaseUrl = "https://github.com/intina47/orbit/tree/main/examples"
const orbitMetadataDocUrl = `${orbitDocsUrl}/metadata`

export function DocsAiSetupFab() {
  const [open, setOpen] = useState(false)
  const [aiTarget, setAiTarget] = useState<AiTarget>("chatgpt")
  const [setupRoute, setSetupRoute] = useState<SetupRoute>("cloud")
  const [language, setLanguage] = useState<LanguageTarget>("nodejs")
  const [appType, setAppType] = useState<AppTarget>("chatbot")
  const [copyStatus, setCopyStatus] = useState("")

  const prompt = useMemo(
    () =>
      buildPrompt({
        aiTarget,
        setupRoute,
        language,
        appType,
      }),
    [aiTarget, setupRoute, language, appType],
  )

  async function copyPrompt() {
    try {
      if (!navigator?.clipboard?.writeText) {
        throw new Error("clipboard not available")
      }
      await navigator.clipboard.writeText(prompt)
      setCopyStatus("Prompt copied")
    } catch {
      setCopyStatus("Copy failed. Select and copy manually.")
    }
  }

  function openAi() {
    if (aiTarget === "cursor") {
      void copyPrompt()
      setCopyStatus("Prompt copied. Paste in Cursor chat.")
      return
    }
    const url = aiUrl(aiTarget, prompt)
    window.open(url, "_blank", "noopener,noreferrer")
  }

  return (
    <div className="fixed left-4 bottom-4 z-50 sm:left-6 sm:bottom-6 max-w-[calc(100vw-2rem)]">
      {open ? (
        <div className="w-[380px] max-w-[calc(100vw-2rem)] border border-border bg-background shadow-2xl">
          <div className="flex items-center justify-between border-b border-border px-4 py-3">
            <div>
              <p className="text-xs tracking-[0.2em] uppercase text-primary">Setup with AI</p>
              <p className="text-xs text-muted-foreground mt-1">Generate a tailored Orbit integration prompt.</p>
            </div>
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="text-xs text-muted-foreground hover:text-foreground transition-colors"
            >
              Close
            </button>
          </div>

          <div className="px-4 py-4 space-y-3">
            <div className="grid grid-cols-2 gap-2">
              <label className="text-xs text-muted-foreground">
                AI
                <select
                  className="mt-1 w-full border border-border bg-secondary px-2 py-2 text-xs text-foreground"
                  value={aiTarget}
                  onChange={(event) => setAiTarget(event.target.value as AiTarget)}
                >
                  {aiTargets.map((target) => (
                    <option key={target.id} value={target.id}>
                      {target.label}
                    </option>
                  ))}
                </select>
              </label>

              <label className="text-xs text-muted-foreground">
                Language
                <select
                  className="mt-1 w-full border border-border bg-secondary px-2 py-2 text-xs text-foreground"
                  value={language}
                  onChange={(event) => setLanguage(event.target.value as LanguageTarget)}
                >
                  {languageTargets.map((target) => (
                    <option key={target.id} value={target.id}>
                      {target.label}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            <div className="grid grid-cols-2 gap-2">
              <label className="text-xs text-muted-foreground">
                Setup route
                <select
                  className="mt-1 w-full border border-border bg-secondary px-2 py-2 text-xs text-foreground"
                  value={setupRoute}
                  onChange={(event) => setSetupRoute(event.target.value as SetupRoute)}
                >
                  <option value="cloud">Orbit Cloud</option>
                  <option value="self_hosted">Self-hosted Orbit API</option>
                </select>
              </label>

              <label className="text-xs text-muted-foreground">
                App type
                <select
                  className="mt-1 w-full border border-border bg-secondary px-2 py-2 text-xs text-foreground"
                  value={appType}
                  onChange={(event) => setAppType(event.target.value as AppTarget)}
                >
                  {appTargets.map((target) => (
                    <option key={target.id} value={target.id}>
                      {target.label}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            <label className="text-xs text-muted-foreground block">
              Prompt to send
              <textarea
                readOnly
                value={prompt}
                rows={12}
                className="mt-1 w-full border border-border bg-secondary px-3 py-2 text-[11px] leading-relaxed text-foreground"
              />
            </label>

            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={copyPrompt}
                className="border border-border px-3 py-1.5 text-xs text-foreground hover:border-primary hover:text-primary transition-colors"
              >
                Copy prompt
              </button>
              <button
                type="button"
                onClick={openAi}
                className="border border-primary bg-primary/10 px-3 py-1.5 text-xs text-primary hover:bg-primary/20 transition-colors"
              >
                {aiTarget === "cursor" ? "Copy for Cursor" : `Open ${labelForAi(aiTarget)}`}
              </button>
              {copyStatus ? <span className="text-[11px] text-muted-foreground">{copyStatus}</span> : null}
            </div>
          </div>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="border border-primary bg-background px-4 py-2 text-xs tracking-wide text-primary hover:bg-primary/10 transition-colors"
        >
          Setup with AI
        </button>
      )}
    </div>
  )
}

function buildPrompt({
  aiTarget,
  setupRoute,
  language,
  appType,
}: {
  aiTarget: AiTarget
  setupRoute: SetupRoute
  language: LanguageTarget
  appType: AppTarget
}): string {
const productContext = [
  "Orbit is memory infrastructure for developer-facing AI products.",
  "Goal: persist user-relevant signals and retrieve focused context with ingest -> retrieve -> feedback.",
  "Official docs: https://orbit-memory.vercel.app/docs",
  "Official repository: https://github.com/intina47/orbit",
  "Monitor `/v1/status` metadata_summary for contested facts, conflict guards, and average fact age.",
]

  const routeInstructions =
    setupRoute === "cloud"
      ? [
          "Use Orbit Cloud with API key auth.",
          "Read ORBIT_API_BASE_URL and ORBIT_API_KEY from environment variables.",
          "Never expose ORBIT_API_KEY in browser JavaScript; keep Orbit calls server-side.",
          "Assume API key format looks like orbit_pk_....",
        ]
      : [
          "Use self-hosted Orbit API (local Docker Compose path).",
          "Use ORBIT_API_BASE_URL=http://localhost:8000 by default.",
          "Use Bearer auth from ORBIT_API_KEY (JWT or orbit_pk key depending on runtime config).",
          "Include local run commands and a health check.",
        ]

  const apiContract = [
    "Use exact Orbit API contracts:",
    "- POST /v1/ingest with JSON body { content, event_type, entity_id, metadata? }",
    "- GET /v1/retrieve with query params query, entity_id, limit (not POST body)",
    "- POST /v1/feedback with JSON body { memory_id, helpful, outcome_value, metadata? }",
    "- Retrieve responses include memories[] with memory_id and content fields",
    "- For assistant writes, use event_type='assistant_response'",
  ]

  const hardValidationRules = [
    "Hard validation rules (must pass):",
    "- Do not implement retrieve as POST or with body fields like content/top_k.",
    "- Do not implement feedback with score/comment-only payloads.",
    "- If helper supports idempotencyKey, send it as the Idempotency-Key header on write endpoints.",
    "- Keep write helper method-aware: ingest/feedback are POST, retrieve is GET.",
    "- Keep secrets server-side only; never put ORBIT_API_KEY in client-side browser code.",
  ]

  const flowRequirements = [
    "Implement the full memory loop: ingest -> retrieve -> assistant answer -> ingest assistant response -> optional feedback.",
    "Use endpoints /v1/ingest, /v1/retrieve, and /v1/feedback.",
    "Keep entity_id stable per user.",
    "Feedback must attach to a retrieved memory_id; do not send entity-level score-only feedback.",
    "Use clear error handling for 401/403/429 and network failures.",
    "Highlight the `/v1/status` metadata_summary counts (contested vs confirmed facts) so the dashboard card mirrors your prompt.",
  ]

  const outputRequirements = [
    "Return complete runnable code with file tree and exact shell commands.",
    "Use a .env file for environment variables.",
    "Include one local verification script or curl sequence that proves memory persistence across two turns.",
    "Include comments only where they clarify non-obvious logic.",
  ]

  const references = [
    "Reference examples (full links):",
    `- ${orbitGithubExamplesBaseUrl}/nodejs_orbit_api_chatbot`,
    `- ${orbitGithubExamplesBaseUrl}/http_api_clients/node_fetch.mjs`,
    `- ${orbitGithubExamplesBaseUrl}/http_api_clients/python_http.py`,
    `- ${orbitGithubExamplesBaseUrl}/http_api_clients/go_http.go`,
    "Reference docs pages:",
    `${orbitDocsUrl}/installation`,
    `${orbitDocsUrl}/rest-endpoints`,
    `${orbitDocsUrl}/examples`,
    `${orbitMetadataDocUrl}`,
  ]

  const targetHint =
    aiTarget === "cursor"
      ? "Make the answer optimized for incremental coding inside Cursor chat."
      : `Format the answer so it can be pasted directly into ${labelForAi(aiTarget)} and executed without guessing missing steps.`

  return [
    `You are a senior ${languageLabel(language)} engineer helping me integrate Orbit memory into a ${appTypeLabel(appType)}.`,
    targetHint,
    "",
    "Product context:",
    ...productContext.map((line) => `- ${line}`),
    "",
    "Constraints:",
    ...routeInstructions.map((line) => `- ${line}`),
    ...apiContract.map((line) => `- ${line}`),
    ...hardValidationRules.map((line) => `- ${line}`),
    ...flowRequirements.map((line) => `- ${line}`),
    ...outputRequirements.map((line) => `- ${line}`),
    "",
    "Use this starter call pattern:",
    languageStarter(language),
    "",
    `Website: ${orbitWebsiteUrl}`,
    `Docs: ${orbitDocsUrl}`,
    `GitHub: ${orbitGithubRepoUrl}`,
    "",
    ...references,
  ].join("\n")
}

function aiUrl(aiTarget: AiTarget, prompt: string): string {
  const encoded = encodeURIComponent(prompt)
  if (aiTarget === "claude") {
    return `https://claude.ai/new?q=${encoded}`
  }
  return `https://chatgpt.com/?q=${encoded}`
}

function labelForAi(aiTarget: AiTarget): string {
  const target = aiTargets.find((item) => item.id === aiTarget)
  return target ? target.label : "AI"
}

function languageLabel(language: LanguageTarget): string {
  const target = languageTargets.find((item) => item.id === language)
  return target ? target.label : "application"
}

function appTypeLabel(appType: AppTarget): string {
  const target = appTargets.find((item) => item.id === appType)
  return target ? target.label.toLowerCase() : "application"
}

function languageStarter(language: LanguageTarget): string {
  if (language === "python") {
    return [
      "```python",
      "import os, requests",
      "headers = {",
      "    'Authorization': f\"Bearer {os.environ['ORBIT_API_KEY']}\",",
      "    'Content-Type': 'application/json',",
      "}",
      "requests.post(f\"{os.environ['ORBIT_API_BASE_URL']}/v1/ingest\", headers=headers, json={",
      "    'content': 'User message',",
      "    'event_type': 'user_question',",
      "    'entity_id': 'alice',",
      "})",
      "```",
    ].join("\n")
  }

  if (language === "go") {
    return [
      "```go",
      `req, _ := http.NewRequest("POST", os.Getenv("ORBIT_API_BASE_URL")+"/v1/ingest", bytes.NewReader(body))`,
      `req.Header.Set("Authorization", "Bearer "+os.Getenv("ORBIT_API_KEY"))`,
      `req.Header.Set("Content-Type", "application/json")`,
      "```",
    ].join("\n")
  }

  if (language === "typescript") {
    return [
      "```ts",
      "const headers = {",
      "  Authorization: `Bearer ${process.env.ORBIT_API_KEY}`,",
      "  'Content-Type': 'application/json',",
      "};",
      "await fetch(`${process.env.ORBIT_API_BASE_URL}/v1/ingest`, {",
      "  method: 'POST',",
      "  headers,",
      "  body: JSON.stringify({ content: 'User message', event_type: 'user_question', entity_id: 'alice' }),",
      "});",
      "```",
    ].join("\n")
  }

  return [
    "```js",
    "const headers = {",
    "  Authorization: `Bearer ${process.env.ORBIT_API_KEY}`,",
    "  'Content-Type': 'application/json',",
    "};",
    "await fetch(`${process.env.ORBIT_API_BASE_URL}/v1/ingest`, {",
    "  method: 'POST',",
    "  headers,",
    "  body: JSON.stringify({ content: 'User message', event_type: 'user_question', entity_id: 'alice' }),",
    "});",
    "```",
  ].join("\n")
}
