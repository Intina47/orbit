import { describe, expect, it } from "vitest";

import { loadConfig } from "../config.js";

describe("loadConfig", () => {
  it("merges identity links from runtime, env, and plugin config", () => {
    const env = {
      ORBIT_API_URL: "http://orbit.local:8000/",
      ORBIT_JWT_TOKEN: "env-token",
      ORBIT_MEMORY_LIMIT: "5",
      ORBIT_ENTITY_PREFIX: "openclaw",
      ORBIT_USER_EVENT_TYPE: "user_prompt",
      ORBIT_ASSISTANT_EVENT_TYPE: "assistant_response",
      ORBIT_CAPTURE_ASSISTANT_OUTPUT: "true",
      ORBIT_PREFER_SESSION_KEY: "true",
      ORBIT_IDENTITY_LINKS_JSON:
        "{\"user:alice\":[\"sms:+15551230000\"],\"user:bob\":[\"email:bob@example.com\"]}",
    } as NodeJS.ProcessEnv;

    const config = loadConfig({
      env,
      runtimeConfig: {
        session: {
          identityLinks: {
            "user:alice": ["discord:alice_dev"],
          },
        },
      },
      pluginConfig: {
        identityLinks: {
          "user:alice": ["wa:+15559870000"],
        },
        orbitPreferSessionKey: false,
        orbitMemoryLimit: 7,
      },
    });

    expect(config.orbitApiUrl).toBe("http://orbit.local:8000");
    expect(config.orbitToken).toBe("env-token");
    expect(config.memoryLimit).toBe(7);
    expect(config.preferSessionKey).toBe(false);
    expect(config.identityLinks["user:alice"]).toEqual([
      "discord:alice_dev",
      "sms:+15551230000",
      "wa:+15559870000",
    ]);
    expect(config.identityLinks["user:bob"]).toEqual(["email:bob@example.com"]);
  });

  it("uses plugin token override when provided", () => {
    const env = {
      ORBIT_API_URL: "http://127.0.0.1:8000",
      ORBIT_JWT_TOKEN: "env-token",
      ORBIT_MEMORY_LIMIT: "5",
      ORBIT_ENTITY_PREFIX: "openclaw",
      ORBIT_USER_EVENT_TYPE: "user_prompt",
      ORBIT_ASSISTANT_EVENT_TYPE: "assistant_response",
      ORBIT_CAPTURE_ASSISTANT_OUTPUT: "true",
      ORBIT_PREFER_SESSION_KEY: "true",
    } as NodeJS.ProcessEnv;

    const config = loadConfig({
      env,
      pluginConfig: {
        orbitJwtToken: "plugin-token",
      },
    });

    expect(config.orbitToken).toBe("plugin-token");
  });
});
