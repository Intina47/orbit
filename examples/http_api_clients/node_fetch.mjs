import dotenv from "dotenv";

dotenv.config();

const baseUrl = requiredEnv("ORBIT_API_BASE_URL").replace(/\/+$/, "");
const apiKey = requiredEnv("ORBIT_API_KEY");
const entityId = process.env.ORBIT_ENTITY_ID || "alice";

async function main() {
  const question = "I keep mixing arrays and objects in JavaScript.";

  const ingest = await orbitRequest("/v1/ingest", {
    method: "POST",
    body: {
      content: question,
      event_type: "user_question",
      entity_id: entityId,
    },
  });

  const retrieval = await orbitRequest(
    `/v1/retrieve?query=${encodeURIComponent(`What should I know about ${entityId}?`)}&entity_id=${encodeURIComponent(entityId)}&limit=5`,
    { method: "GET" },
  );

  console.log("ingest.memory_id =", ingest.memory_id);
  console.log("retrieved =", (retrieval.memories || []).length, "memories");
  for (const memory of retrieval.memories || []) {
    console.log("-", memory.content);
  }
}

async function orbitRequest(path, { method, body }) {
  const response = await fetch(`${baseUrl}${path}`, {
    method,
    headers: {
      Authorization: `Bearer ${apiKey}`,
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: body ? JSON.stringify(body) : undefined,
  });

  const text = await response.text();
  const payload = text ? safeJsonParse(text) : {};
  if (!response.ok) {
    throw new Error(payload.detail || text || `HTTP ${response.status}`);
  }
  return payload;
}

function safeJsonParse(text) {
  try {
    return JSON.parse(text);
  } catch {
    return {};
  }
}

function requiredEnv(name) {
  const value = process.env[name]?.trim();
  if (!value) {
    throw new Error(`Missing environment variable: ${name}`);
  }
  return value;
}

main().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
