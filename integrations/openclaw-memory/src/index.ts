import { z } from "zod";

import { loadConfig } from "./config.js";
import { formatRetrievedMemories } from "./format.js";
import { resolveEntityId } from "./identity.js";
import { OrbitClient } from "./orbit-client.js";
import type {
  HookContext,
  HookEvent,
  OpenClawCommandDefinition,
  OpenClawPlugin,
  OpenClawPluginApi,
  OpenClawToolDefinition,
  OpenClawToolRegistrationOptions,
  JsonObject,
} from "./types.js";

const CONTEXT_MARKER = "Orbit memory context (already ranked):";

const DEFAULT_VERSION = "0.2.0";

const pluginConfigSchema: JsonObject = {
  type: "object",
  properties: {
    orbitApiUrl: {
      type: "string",
      description: "Orbit API base URL.",
      default: "http://127.0.0.1:8000",
    },
    orbitJwtToken: {
      type: "string",
      description: "Bearer JWT used for Orbit API authentication.",
    },
    orbitMemoryLimit: {
      type: "number",
      minimum: 1,
      maximum: 20,
      default: 5,
    },
    orbitEntityPrefix: {
      type: "string",
      default: "openclaw",
    },
    orbitUserEventType: {
      type: "string",
      default: "user_prompt",
    },
    orbitAssistantEventType: {
      type: "string",
      default: "assistant_response",
    },
    orbitCaptureAssistantOutput: {
      type: "boolean",
      default: true,
    },
    orbitPreferSessionKey: {
      type: "boolean",
      default: true,
      description: "Use OpenClaw sessionKey as primary Orbit entity_id.",
    },
    identityLinks: {
      type: "object",
      additionalProperties: {
        type: "array",
        items: { type: "string" },
      },
      description: "Canonical identity to alias map for cross-channel entity stitching.",
    },
  },
};

const recallSchema = z.object({
  query: z.string().min(1),
  entity_id: z.string().min(1).optional(),
  limit: z.number().int().min(1).max(20).optional(),
});

const feedbackSchema = z.object({
  memory_id: z.string().min(1),
  helpful: z.boolean(),
  outcome_value: z.number().optional(),
});

const recallToolInputSchema: JsonObject = {
  type: "object",
  properties: {
    query: { type: "string", minLength: 1 },
    entity_id: { type: "string", minLength: 1 },
    limit: { type: "number", minimum: 1, maximum: 20 },
  },
  required: ["query"],
};

const feedbackToolInputSchema: JsonObject = {
  type: "object",
  properties: {
    memory_id: { type: "string", minLength: 1 },
    helpful: { type: "boolean" },
    outcome_value: { type: "number" },
  },
  required: ["memory_id", "helpful"],
};

function readPath(source: unknown, path: ReadonlyArray<string>): unknown {
  let current: unknown = source;
  for (const segment of path) {
    if (typeof current !== "object" || current === null) {
      return undefined;
    }
    current = (current as Record<string, unknown>)[segment];
  }
  return current;
}

function getFirstText(
  sources: ReadonlyArray<unknown>,
  paths: ReadonlyArray<ReadonlyArray<string>>,
): string | null {
  for (const source of sources) {
    for (const path of paths) {
      const candidate = readPath(source, path);
      if (typeof candidate === "string" && candidate.trim().length > 0) {
        return candidate.trim();
      }
    }
  }
  return null;
}

function extractInput(event: HookEvent, context: HookContext): string | null {
  return getFirstText([event, context], [
    ["input"],
    ["prompt"],
    ["message"],
    ["request", "input"],
    ["data", "input"],
    ["data", "prompt"],
    ["data", "message"],
  ]);
}

function extractOutput(event: HookEvent, context: HookContext): string | null {
  return getFirstText([event, context], [
    ["result", "output_text"],
    ["result", "output"],
    ["result", "content"],
    ["output"],
    ["data", "result", "output_text"],
    ["data", "result", "output"],
    ["data", "result", "content"],
    ["data", "output"],
  ]);
}

function stripInjectedMemoryContext(value: string): string {
  const markerIndex = value.indexOf(CONTEXT_MARKER);
  if (markerIndex < 0) {
    return value.trim();
  }
  return value.slice(0, markerIndex).trim();
}

function appendInputContext(
  event: HookEvent,
  existingInput: string,
  memoryBlock: string,
): HookEvent {
  const existing = existingInput.trim();
  if (!existing || existing.includes(CONTEXT_MARKER)) {
    return event;
  }
  const nextInput = `${existing}\n\n${memoryBlock}`;

  const dataField = readPath(event, ["data"]);
  if (typeof dataField === "object" && dataField !== null) {
    return {
      ...event,
      data: { ...(dataField as JsonObject), input: nextInput },
    };
  }
  return { ...event, input: nextInput };
}

function appendRetrievedMemoryIds(event: HookEvent, memoryIds: string[]): HookEvent {
  if (memoryIds.length === 0) {
    return event;
  }
  const metadata = readPath(event, ["metadata"]);
  if (typeof metadata === "object" && metadata !== null) {
    return {
      ...event,
      metadata: {
        ...(metadata as JsonObject),
        orbit_memory_ids: memoryIds,
      },
    };
  }
  return {
    ...event,
    metadata: { orbit_memory_ids: memoryIds },
  };
}

function log(api: OpenClawPluginApi, level: "info" | "warn" | "error", ...args: unknown[]): void {
  const logger = api.logger?.[level];
  if (logger) {
    logger(...args);
    return;
  }
  api.log(...args);
}

function registerHook(
  api: OpenClawPluginApi,
  eventName: string,
  handler: (event: HookEvent, context: HookContext) => Promise<HookEvent | void>,
): void {
  if (api.on) {
    api.on(eventName, handler);
    return;
  }
  if (api.registerHook) {
    try {
      api.registerHook(eventName, handler);
      return;
    } catch {
      api.registerHook(eventName, async (context: HookContext) => {
        const next = await handler({}, context);
        if (next && typeof next === "object") {
          return next as HookContext;
        }
        return context;
      });
      return;
    }
  }
  log(api, "warn", `[orbit] hook registration unavailable for event '${eventName}'.`);
}

function registerCommand(
  api: OpenClawPluginApi,
  definition: OpenClawCommandDefinition,
): void {
  if (!api.registerCommand) {
    return;
  }
  try {
    api.registerCommand(definition);
  } catch {
    api.registerCommand(definition.name, definition.execute);
  }
}

function registerTool(
  api: OpenClawPluginApi,
  definition: OpenClawToolDefinition,
  options: OpenClawToolRegistrationOptions = { requiresAuth: true },
): void {
  if (!api.registerTool) {
    return;
  }
  try {
    api.registerTool(definition, options);
    return;
  } catch {
    api.registerTool(
      definition.name,
      definition.description,
      definition.inputSchema,
      definition.execute,
    );
  }
}

function buildRetrieveQuery(input: string): string {
  const compact = input.replace(/\s+/g, " ").trim();
  const max = 420;
  return compact.length <= max ? compact : compact.slice(0, max);
}

async function registerPlugin(api: OpenClawPluginApi): Promise<void> {
  const config = loadConfig({
    env: process.env,
    pluginConfig: api.pluginConfig,
    runtimeConfig: api.config,
  });
  const client = new OrbitClient(config, (...args: unknown[]) => log(api, "info", ...args));

  log(
    api,
    "info",
    `[orbit] plugin init base_url=${config.orbitApiUrl} limit=${config.memoryLimit} token_set=${config.orbitToken.length > 0}`,
  );

  registerCommand(api, {
    name: "orbit-memory-status",
    description: "Returns Orbit status for plugin diagnostics.",
    execute: async () => {
      try {
        const status = await client.status();
        return JSON.stringify(status, null, 2);
      } catch (error) {
        const message =
          error instanceof Error ? error.message : "unknown Orbit status error";
        return `Orbit status failed: ${message}`;
      }
    },
  });

  registerTool(
    api,
    {
      name: "orbit_recall",
      description: "Retrieve top Orbit memories for the active user context.",
      inputSchema: recallToolInputSchema,
      execute: async (rawArgs: JsonObject) => {
        const args = recallSchema.parse(rawArgs);
        const entityId = args.entity_id ?? `${config.entityPrefix}:manual`;
        const memories = await client.retrieve({
          query: args.query,
          entityId,
          limit: args.limit ?? config.memoryLimit,
        });
        return {
          entity_id: entityId,
          count: memories.length,
          memories,
        };
      },
    },
    { requiresAuth: true },
  );

  registerTool(
    api,
    {
      name: "orbit_feedback",
      description: "Send memory quality feedback signal to Orbit.",
      inputSchema: feedbackToolInputSchema,
      execute: async (rawArgs: JsonObject) => {
        const args = feedbackSchema.parse(rawArgs);
        const feedbackInput: {
          memoryId: string;
          helpful: boolean;
          outcomeValue?: number;
        } = {
          memoryId: args.memory_id,
          helpful: args.helpful,
        };
        if (typeof args.outcome_value === "number") {
          feedbackInput.outcomeValue = args.outcome_value;
        }
        await client.feedback(feedbackInput);
        return { recorded: true };
      },
    },
    { requiresAuth: true },
  );

  registerHook(api, "before_agent_start", async (event: HookEvent, context: HookContext) => {
    const input = extractInput(event, context);
    if (!input) {
      return event;
    }

    const entityId = resolveEntityId({
      event,
      context,
      entityPrefix: config.entityPrefix,
      preferSessionKey: config.preferSessionKey,
      identityLinks: config.identityLinks,
    });

    try {
      const memories = await client.retrieve({
        query: buildRetrieveQuery(input),
        entityId,
        limit: config.memoryLimit,
      });
      const memoryBlock = formatRetrievedMemories(memories);
      if (!memoryBlock) {
        return event;
      }
      const augmented = appendInputContext(event, input, memoryBlock);
      return appendRetrievedMemoryIds(
        augmented,
        memories.map((memory) => memory.memory_id),
      );
    } catch (error) {
      log(api, "warn", "[orbit] before_agent_start retrieval failed:", error);
      return event;
    }
  });

  registerHook(api, "agent_end", async (event: HookEvent, context: HookContext) => {
    const entityId = resolveEntityId({
      event,
      context,
      entityPrefix: config.entityPrefix,
      preferSessionKey: config.preferSessionKey,
      identityLinks: config.identityLinks,
    });
    const input = extractInput(event, context);
    const output = extractOutput(event, context);

    try {
      const cleanInput = input ? stripInjectedMemoryContext(input) : "";
      if (cleanInput) {
        await client.ingest({
          content: cleanInput,
          entityId,
          eventType: config.userEventType,
          metadata: { source: "openclaw", role: "user" },
        });
      }
      if (config.captureAssistantOutput && output) {
        await client.ingest({
          content: output,
          entityId,
          eventType: config.assistantEventType,
          metadata: { source: "openclaw", role: "assistant" },
        });
      }
    } catch (error) {
      log(api, "warn", "[orbit] agent_end ingest failed:", error);
    }

    return event;
  });
}

const plugin: OpenClawPlugin = {
  id: "orbit.memory",
  kind: "memory",
  name: "@orbit/openclaw-memory",
  version: DEFAULT_VERSION,
  description: "Orbit-backed memory slot for OpenClaw agents.",
  configSchema: pluginConfigSchema,
  slots: {
    memory: {
      title: "Orbit Memory",
      description: "Adaptive memory retrieval from Orbit API.",
    },
  },
  register: registerPlugin,
  init: registerPlugin,
};

export default plugin;
