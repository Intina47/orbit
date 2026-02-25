import path from "node:path";
import { fileURLToPath } from "node:url";

import dotenv from "dotenv";
import express from "express";

dotenv.config();

const app = express();
app.use(express.json({ limit: "1mb" }));

const port = toPositiveInt(process.env.PORT, 8030);
const orbitApiBaseUrl = normalizeBaseUrl(
  process.env.ORBIT_API_BASE_URL,
  "http://localhost:8000",
);
const orbitApiKey = (process.env.ORBIT_API_KEY ?? "").trim();
const retrieveLimit = Math.max(1, Math.min(toPositiveInt(process.env.ORBIT_RETRIEVE_LIMIT, 5), 10));
const ollamaHost = normalizeBaseUrl(process.env.OLLAMA_HOST, "http://localhost:11434");
const ollamaModel = (process.env.OLLAMA_MODEL ?? "llama3.1").trim() || "llama3.1";

if (!orbitApiKey) {
  console.error("Missing ORBIT_API_KEY. Set it in .env before running this example.");
  process.exit(1);
}

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
app.use(express.static(path.join(__dirname, "public")));

app.get("/api/health", async (_request, response) => {
  try {
    const data = await orbitRequest("/v1/health", { method: "GET" });
    response.json({
      ok: true,
      orbit: data,
    });
  } catch (error) {
    response.status(502).json({
      ok: false,
      detail: toErrorMessage(error),
    });
  }
});

app.get("/api/status", async (_request, response) => {
  try {
    const data = await orbitRequest("/v1/status", { method: "GET" });
    response.json(data);
  } catch (error) {
    response.status(502).json({
      detail: toErrorMessage(error),
    });
  }
});

app.post("/api/chat", async (request, response) => {
  try {
    const userId = normalizeNonEmpty(request.body?.userId, "demo-user");
    const message = normalizeNonEmpty(request.body?.message);
    if (!message) {
      response.status(400).json({ detail: "message is required" });
      return;
    }

    await orbitRequest("/v1/ingest", {
      method: "POST",
      body: {
        content: message,
        event_type: "user_question",
        entity_id: userId,
      },
    });

    const retrieval = await orbitRequest("/v1/retrieve", {
      method: "GET",
      query: {
        query: `What should I know about ${userId} to help with: ${message}`,
        entity_id: userId,
        limit: String(retrieveLimit),
      },
    });
    const context = Array.isArray(retrieval.memories) ? retrieval.memories : [];
    const systemPrompt = buildSystemPrompt({
      userId,
      context,
      userMessage: message,
    });

    const generated = await generateAssistantReply({
      userMessage: message,
      systemPrompt,
    });
    const assistantText = generated.text;

    const assistantIngest = await orbitRequest("/v1/ingest", {
      method: "POST",
      body: {
        content: assistantText,
        event_type: "assistant_response",
        entity_id: userId,
        metadata: {
          source: "nodejs_orbit_api_chatbot",
          generation_mode: generated.mode,
          model: generated.model,
          context_memory_ids: context.map((memory) => memory.memory_id).filter(Boolean),
        },
      },
    });

    response.json({
      response: assistantText,
      generation_mode: generated.mode,
      context_items: context.length,
      memory_ids: context.map((memory) => memory.memory_id).filter(Boolean),
      assistant_memory_id: assistantIngest.memory_id,
    });
  } catch (error) {
    response.status(502).json({
      detail: toErrorMessage(error),
    });
  }
});

app.post("/api/feedback", async (request, response) => {
  try {
    const memoryId = normalizeNonEmpty(request.body?.memoryId);
    if (!memoryId) {
      response.status(400).json({ detail: "memoryId is required" });
      return;
    }

    const helpful = Boolean(request.body?.helpful);
    const outcomeValue = helpful ? 1.0 : -1.0;
    const feedback = await orbitRequest("/v1/feedback", {
      method: "POST",
      body: {
        memory_id: memoryId,
        helpful,
        outcome_value: outcomeValue,
      },
    });
    response.json({
      recorded: feedback.recorded === true,
      memory_id: memoryId,
      helpful,
    });
  } catch (error) {
    response.status(502).json({
      detail: toErrorMessage(error),
    });
  }
});

app.listen(port, () => {
  console.log(`Node.js Orbit API chatbot running: http://localhost:${port}`);
  console.log(`Orbit API: ${orbitApiBaseUrl}`);
  console.log(`Ollama host: ${ollamaHost}`);
});

async function generateAssistantReply({ userMessage, systemPrompt }) {
  try {
    const payload = await jsonRequest(`${ollamaHost}/api/chat`, {
      method: "POST",
      body: {
        model: ollamaModel,
        stream: false,
        messages: [
          { role: "system", content: systemPrompt },
          { role: "user", content: userMessage },
        ],
      },
      headers: {},
      timeoutMs: 20_000,
    });
    const content = normalizeNonEmpty(payload?.message?.content);
    if (content) {
      return {
        text: content,
        mode: "ollama",
        model: ollamaModel,
      };
    }
  } catch (error) {
    console.warn("Ollama unavailable, falling back to deterministic response:", toErrorMessage(error));
  }
  return {
    text: buildFallbackReply(userMessage),
    mode: "fallback",
    model: "deterministic-template",
  };
}

function buildSystemPrompt({ userId, context, userMessage }) {
  const contextLines = context
    .slice(0, retrieveLimit)
    .map((memory, index) => {
      const content = normalizeNonEmpty(memory?.content, "unknown");
      return `${index + 1}. ${content}`;
    });
  const contextBlock = contextLines.length > 0 ? contextLines.join("\n") : "No prior memory yet.";
  return [
    "You are a practical coding coach.",
    "Use memory context where relevant, but stay concise.",
    `User id: ${userId}`,
    "",
    "Memory context:",
    contextBlock,
    "",
    `Current question: ${userMessage}`,
  ].join("\n");
}

function buildFallbackReply(userMessage) {
  const trimmed = normalizeNonEmpty(userMessage, "your question");
  return [
    `You asked: "${trimmed}".`,
    "Quick plan:",
    "1) Clarify the goal in one sentence.",
    "2) Break it into 2-3 small steps.",
    "3) Implement the smallest runnable version first.",
    "If Ollama is running, responses will become fully model-generated.",
  ].join("\n");
}

async function orbitRequest(pathname, { method, body = undefined, query = undefined }) {
  const url = new URL(pathname, `${orbitApiBaseUrl}/`);
  if (query && typeof query === "object") {
    for (const [key, value] of Object.entries(query)) {
      if (value === undefined || value === null) {
        continue;
      }
      url.searchParams.set(key, String(value));
    }
  }

  return jsonRequest(url.toString(), {
    method,
    body,
    timeoutMs: 15_000,
    headers: {
      Authorization: `Bearer ${orbitApiKey}`,
      Accept: "application/json",
    },
  });
}

async function jsonRequest(url, { method, body = undefined, headers = {}, timeoutMs = 15_000 }) {
  const controller = new AbortController();
  const timeoutHandle = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const resolvedHeaders = new Headers(headers);
    if (body !== undefined) {
      resolvedHeaders.set("Content-Type", "application/json");
    }
    const response = await fetch(url, {
      method,
      headers: resolvedHeaders,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: controller.signal,
    });
    const text = await response.text();
    const parsed = parseJson(text);
    if (!response.ok) {
      const detail = resolveErrorDetail(parsed, text, response.status);
      throw new Error(detail);
    }
    return parsed;
  } finally {
    clearTimeout(timeoutHandle);
  }
}

function parseJson(text) {
  const normalized = text?.trim();
  if (!normalized) {
    return {};
  }
  try {
    return JSON.parse(normalized);
  } catch {
    return {};
  }
}

function resolveErrorDetail(parsed, fallbackText, statusCode) {
  if (parsed && typeof parsed === "object") {
    const detail = parsed.detail;
    if (typeof detail === "string" && detail.trim()) {
      return detail.trim();
    }
    if (detail && typeof detail === "object" && typeof detail.message === "string") {
      return detail.message.trim();
    }
  }
  if (typeof fallbackText === "string" && fallbackText.trim()) {
    return fallbackText.trim();
  }
  return `Request failed with status ${statusCode}`;
}

function normalizeBaseUrl(raw, fallback) {
  const candidate = (raw ?? "").trim();
  const resolved = candidate || fallback;
  return resolved.replace(/\/+$/, "");
}

function normalizeNonEmpty(raw, fallback = "") {
  if (raw === undefined || raw === null) {
    return fallback;
  }
  const normalized = String(raw).trim();
  return normalized || fallback;
}

function toPositiveInt(raw, fallback) {
  const parsed = Number.parseInt(String(raw ?? ""), 10);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return fallback;
  }
  return parsed;
}

function toErrorMessage(error) {
  if (error instanceof Error) {
    return error.message;
  }
  return String(error);
}
