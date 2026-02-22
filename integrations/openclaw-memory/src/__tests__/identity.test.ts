import { describe, expect, it } from "vitest";

import { resolveEntityId } from "../identity.js";

describe("resolveEntityId", () => {
  it("uses identity links to collapse session aliases into one canonical id", () => {
    const entityId = resolveEntityId({
      event: {
        sessionKey: "wa:+15550001111",
        origin: "whatsapp",
      },
      context: {},
      entityPrefix: "openclaw",
      preferSessionKey: true,
      identityLinks: {
        "user:alice": ["wa:+15550001111", "telegram:@alice"],
      },
    });

    expect(entityId).toBe("user:alice");
  });

  it("prefers raw session key when configured and no identity link match exists", () => {
    const entityId = resolveEntityId({
      event: { sessionKey: "session-42" },
      context: {},
      entityPrefix: "openclaw",
      preferSessionKey: true,
      identityLinks: {},
    });

    expect(entityId).toBe("session-42");
  });

  it("falls back to prefixed user id with channel when session key is absent", () => {
    const entityId = resolveEntityId({
      event: {
        userId: "alice",
        channel: "discord",
      },
      context: {},
      entityPrefix: "openclaw",
      preferSessionKey: true,
      identityLinks: {},
    });

    expect(entityId).toBe("openclaw:discord:alice");
  });

  it("returns anonymous fallback when no identity signals exist", () => {
    const entityId = resolveEntityId({
      event: {},
      context: {},
      entityPrefix: "openclaw",
      preferSessionKey: true,
      identityLinks: {},
    });

    expect(entityId).toBe("openclaw:anonymous");
  });
});
