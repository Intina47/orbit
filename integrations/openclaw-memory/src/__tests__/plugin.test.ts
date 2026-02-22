import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import plugin from "../index.js";
import type {
  HookCallback,
  OpenClawCommandDefinition,
  OpenClawPluginApi,
  OpenClawToolDefinition,
  OpenClawToolRegistrationOptions,
} from "../types.js";

type EventPayload = Record<string, unknown>;

interface TestApiRegistry {
  hooks: Map<string, HookCallback>;
  commands: Map<
    string,
    (args: string, context?: EventPayload) => Promise<string> | string
  >;
  tools: Map<string, OpenClawToolDefinition["execute"]>;
}

const ENV_KEYS = [
  "ORBIT_API_URL",
  "ORBIT_JWT_TOKEN",
  "ORBIT_MEMORY_LIMIT",
  "ORBIT_ENTITY_PREFIX",
  "ORBIT_USER_EVENT_TYPE",
  "ORBIT_ASSISTANT_EVENT_TYPE",
  "ORBIT_CAPTURE_ASSISTANT_OUTPUT",
  "ORBIT_PREFER_SESSION_KEY",
] as const;

function jsonResponse(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function createApi(): { api: OpenClawPluginApi; registry: TestApiRegistry } {
  const hooks = new Map<string, HookCallback>();
  const commands = new Map<
    string,
    (args: string, context?: EventPayload) => Promise<string> | string
  >();
  const tools = new Map<string, OpenClawToolDefinition["execute"]>();

  const api: OpenClawPluginApi = {
    log: vi.fn(),
    logger: {
      info: vi.fn(),
      warn: vi.fn(),
      error: vi.fn(),
      debug: vi.fn(),
    },
    pluginConfig: {
      identityLinks: {
        "user:alice": ["wa:+15550001111"],
      },
      orbitMemoryLimit: 5,
    },
    registerCommand: (
      definitionOrName: OpenClawCommandDefinition | string,
      legacyHandler?: (args: string, context?: EventPayload) => Promise<string> | string,
    ) => {
      if (typeof definitionOrName === "string") {
        if (!legacyHandler) {
          throw new Error("legacy command handler missing");
        }
        commands.set(definitionOrName, legacyHandler);
        return;
      }
      if (definitionOrName.execute) {
        commands.set(definitionOrName.name, definitionOrName.execute);
        return;
      }
      if (definitionOrName.handler) {
        const handler = definitionOrName.handler;
        commands.set(definitionOrName.name, (args: string, context?: EventPayload) =>
          handler({ ...(context ?? {}), args }),
        );
        return;
      }
      throw new Error("command definition missing execute/handler");
    },
    registerTool: (
      definitionOrName: OpenClawToolDefinition | string,
      descriptionOrOptions?: string | OpenClawToolRegistrationOptions,
      legacyInputSchema?: Record<string, unknown>,
      legacyHandler?: (args: EventPayload) => Promise<unknown> | unknown,
    ) => {
      if (typeof definitionOrName === "string") {
        if (!legacyHandler || !legacyInputSchema || typeof descriptionOrOptions !== "string") {
          throw new Error("legacy tool signature is incomplete");
        }
        tools.set(definitionOrName, legacyHandler);
        return;
      }
      if (
        descriptionOrOptions &&
        typeof descriptionOrOptions === "object" &&
        "requiresAuth" in descriptionOrOptions
      ) {
        // no-op; verified by type compatibility
      }
      tools.set(definitionOrName.name, definitionOrName.execute);
    },
    on: (event: string, handler: HookCallback) => {
      hooks.set(event, handler);
    },
  };

  return {
    api,
    registry: { hooks, commands, tools },
  };
}

async function registerPlugin(api: OpenClawPluginApi): Promise<void> {
  const registerFn = plugin.register ?? plugin.init;
  if (!registerFn) {
    throw new Error("plugin has no register/init function");
  }
  await registerFn(api);
}

describe("openclaw orbit plugin", () => {
  let envSnapshot: Record<string, string | undefined> = {};

  beforeEach(() => {
    envSnapshot = Object.fromEntries(ENV_KEYS.map((key) => [key, process.env[key]]));
    process.env.ORBIT_API_URL = "http://127.0.0.1:8000";
    process.env.ORBIT_JWT_TOKEN = "test-token";
    process.env.ORBIT_MEMORY_LIMIT = "5";
    process.env.ORBIT_ENTITY_PREFIX = "openclaw";
    process.env.ORBIT_USER_EVENT_TYPE = "user_prompt";
    process.env.ORBIT_ASSISTANT_EVENT_TYPE = "assistant_response";
    process.env.ORBIT_CAPTURE_ASSISTANT_OUTPUT = "true";
    process.env.ORBIT_PREFER_SESSION_KEY = "true";
  });

  afterEach(() => {
    for (const key of ENV_KEYS) {
      const value = envSnapshot[key];
      if (typeof value === "undefined") {
        delete process.env[key];
      } else {
        process.env[key] = value;
      }
    }
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("retrieves context on before_agent_start and ingests clean data on agent_end", async () => {
    const fetchMock = vi.fn(async (input: string | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/v1/retrieve")) {
        return jsonResponse({
          memories: [
            {
              memory_id: "m1",
              content: "Alice prefers concise explanations.",
              event_type: "inferred_preference",
            },
          ],
        });
      }
      if (url.includes("/v1/ingest")) {
        const body = init?.body ? JSON.parse(String(init.body)) : {};
        return jsonResponse({
          stored: true,
          memory_id: body.event_type === "user_prompt" ? "u1" : "a1",
        });
      }
      throw new Error(`unexpected url ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const { api, registry } = createApi();
    await registerPlugin(api);

    const beforeHook = registry.hooks.get("before_agent_start");
    const endHook = registry.hooks.get("agent_end");

    expect(beforeHook).toBeDefined();
    expect(endHook).toBeDefined();

    const beforeEvent: EventPayload = {
      input: "How do I write Python for loops?",
      sessionKey: "wa:+15550001111",
      origin: "whatsapp",
    };
    const beforeResult = await beforeHook?.(beforeEvent, {});
    expect(beforeResult).toBeDefined();

    const updatedEvent = beforeResult as EventPayload;
    expect(String(updatedEvent.input)).toContain("Orbit memory context (already ranked):");
    const metadata = (updatedEvent.metadata ?? {}) as Record<string, unknown>;
    expect(metadata.orbit_memory_ids).toEqual(["m1"]);

    const retrieveUrl = String(fetchMock.mock.calls[0]?.[0] ?? "");
    expect(retrieveUrl).toContain("/v1/retrieve");
    expect(retrieveUrl).toContain("entity_id=user%3Aalice");

    const endEvent: EventPayload = {
      ...updatedEvent,
      result: {
        output: "Use `for i in range(n)` when iterating predictable counts.",
      },
    };
    await endHook?.(endEvent, {});

    expect(fetchMock).toHaveBeenCalledTimes(3);
    const firstIngestInit = fetchMock.mock.calls[1]?.[1] as RequestInit;
    const secondIngestInit = fetchMock.mock.calls[2]?.[1] as RequestInit;

    const firstBody = JSON.parse(String(firstIngestInit.body)) as Record<string, unknown>;
    const secondBody = JSON.parse(String(secondIngestInit.body)) as Record<string, unknown>;

    expect(firstBody.entity_id).toBe("user:alice");
    expect(firstBody.event_type).toBe("user_prompt");
    expect(String(firstBody.content)).toBe("How do I write Python for loops?");
    expect(String(firstBody.content)).not.toContain("Orbit memory context");

    expect(secondBody.entity_id).toBe("user:alice");
    expect(secondBody.event_type).toBe("assistant_response");
  });

  it("registers a status command that returns Orbit status", async () => {
    const fetchMock = vi.fn(async (input: string | URL) => {
      const url = String(input);
      if (url.includes("/v1/status")) {
        return jsonResponse({
          status: "ok",
          uptime_seconds: 42,
        });
      }
      throw new Error(`unexpected url ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const { api, registry } = createApi();
    await registerPlugin(api);

    const statusCommand = registry.commands.get("orbit-memory-status");
    expect(statusCommand).toBeDefined();

    const statusText = await statusCommand?.("", {});
    expect(typeof statusText).toBe("string");
    expect(String(statusText)).toContain("\"status\": \"ok\"");
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
