import { z } from "zod";

import type { JsonObject } from "./types.js";

const rawConfigSchema = z.object({
  ORBIT_API_URL: z.string().default("http://127.0.0.1:8000"),
  ORBIT_JWT_TOKEN: z.string().optional(),
  ORBIT_API_KEY: z.string().optional(),
  ORBIT_MEMORY_LIMIT: z.string().default("5"),
  ORBIT_ENTITY_PREFIX: z.string().default("openclaw"),
  ORBIT_USER_EVENT_TYPE: z.string().default("user_prompt"),
  ORBIT_ASSISTANT_EVENT_TYPE: z.string().default("assistant_response"),
  ORBIT_CAPTURE_ASSISTANT_OUTPUT: z.string().default("true"),
  ORBIT_PREFER_SESSION_KEY: z.string().default("true"),
  ORBIT_IDENTITY_LINKS_JSON: z.string().optional(),
});

export type IdentityLinksMap = Record<string, string[]>;

export interface OrbitPluginConfig {
  orbitApiUrl: string;
  orbitToken: string;
  memoryLimit: number;
  entityPrefix: string;
  userEventType: string;
  assistantEventType: string;
  captureAssistantOutput: boolean;
  preferSessionKey: boolean;
  identityLinks: IdentityLinksMap;
}

export interface LoadConfigOptions {
  env?: NodeJS.ProcessEnv;
  pluginConfig?: JsonObject;
  runtimeConfig?: JsonObject;
}

function normalizeBaseUrl(value: string): string {
  return value.trim().replace(/\/+$/, "");
}

function parseBoolean(value: string): boolean {
  return value.trim().toLowerCase() !== "false";
}

function parsePositiveInteger(value: string, fallback: number): number {
  const parsed = Number.parseInt(value, 10);
  if (Number.isNaN(parsed) || parsed < 1) {
    return fallback;
  }
  return parsed;
}

function asObject(value: unknown): JsonObject | null {
  if (typeof value !== "object" || value === null) {
    return null;
  }
  return value as JsonObject;
}

function readPath(source: unknown, path: ReadonlyArray<string>): unknown {
  let current: unknown = source;
  for (const segment of path) {
    if (typeof current !== "object" || current === null) {
      return undefined;
    }
    current = (current as JsonObject)[segment];
  }
  return current;
}

function asString(value: unknown): string | null {
  if (typeof value !== "string") {
    return null;
  }
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
}

function asNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === "string") {
    const parsed = Number.parseInt(value, 10);
    if (!Number.isNaN(parsed)) {
      return parsed;
    }
  }
  return null;
}

function asBoolean(value: unknown): boolean | null {
  if (typeof value === "boolean") {
    return value;
  }
  if (typeof value === "string") {
    return value.trim().toLowerCase() !== "false";
  }
  return null;
}

function parseIdentityLinks(value: unknown): IdentityLinksMap {
  const source = asObject(value);
  if (!source) {
    return {};
  }
  const parsed: IdentityLinksMap = {};
  for (const [canonicalIdentity, aliases] of Object.entries(source)) {
    const canonical = canonicalIdentity.trim();
    if (canonical.length === 0) {
      continue;
    }
    if (Array.isArray(aliases)) {
      const values = aliases
        .map((alias) => (typeof alias === "string" ? alias.trim() : ""))
        .filter((alias) => alias.length > 0);
      if (values.length > 0) {
        parsed[canonical] = values;
      }
      continue;
    }
    if (typeof aliases === "string" && aliases.trim().length > 0) {
      parsed[canonical] = [aliases.trim()];
    }
  }
  return parsed;
}

function parseIdentityLinksFromEnv(raw: string | null | undefined): IdentityLinksMap {
  if (!raw || raw.trim().length === 0) {
    return {};
  }
  try {
    const parsed = JSON.parse(raw);
    return parseIdentityLinks(parsed);
  } catch {
    return {};
  }
}

function mergeIdentityLinks(
  ...sources: ReadonlyArray<IdentityLinksMap>
): IdentityLinksMap {
  const merged: IdentityLinksMap = {};
  for (const source of sources) {
    for (const [canonical, aliases] of Object.entries(source)) {
      const existing = merged[canonical] ?? [];
      const seen = new Set(existing);
      for (const alias of aliases) {
        if (!seen.has(alias)) {
          existing.push(alias);
          seen.add(alias);
        }
      }
      merged[canonical] = existing;
    }
  }
  return merged;
}

function getPluginConfig(source: JsonObject | undefined): JsonObject {
  return asObject(source) ?? {};
}

function getRuntimeSessionIdentityLinks(source: JsonObject | undefined): IdentityLinksMap {
  const fromSession = parseIdentityLinks(readPath(source, ["session", "identityLinks"]));
  const fromIdentityLinks = parseIdentityLinks(readPath(source, ["identityLinks"]));
  return mergeIdentityLinks(fromSession, fromIdentityLinks);
}

export function loadConfig(options: LoadConfigOptions = {}): OrbitPluginConfig {
  const env = options.env ?? process.env;
  const parsed = rawConfigSchema.parse(env);
  const pluginConfig = getPluginConfig(options.pluginConfig);
  const runtimeConfig = asObject(options.runtimeConfig) ?? {};

  const apiUrl = asString(pluginConfig.orbitApiUrl) ?? parsed.ORBIT_API_URL;
  const pluginToken =
    asString(pluginConfig.orbitJwtToken) ?? asString(pluginConfig.orbitApiKey);
  const token =
    pluginToken ?? (parsed.ORBIT_JWT_TOKEN ?? parsed.ORBIT_API_KEY ?? "").trim();

  const limitNumber = asNumber(pluginConfig.orbitMemoryLimit);
  const memoryLimit =
    limitNumber !== null
      ? parsePositiveInteger(String(limitNumber), 5)
      : parsePositiveInteger(parsed.ORBIT_MEMORY_LIMIT, 5);

  const identityLinksFromPlugin = parseIdentityLinks(pluginConfig.identityLinks);
  const identityLinksFromRuntime = getRuntimeSessionIdentityLinks(runtimeConfig);
  const identityLinksFromEnv = parseIdentityLinksFromEnv(parsed.ORBIT_IDENTITY_LINKS_JSON);

  const preferSessionKey =
    asBoolean(pluginConfig.orbitPreferSessionKey) ??
    parseBoolean(parsed.ORBIT_PREFER_SESSION_KEY);
  const entityPrefix = asString(pluginConfig.orbitEntityPrefix) ?? parsed.ORBIT_ENTITY_PREFIX.trim();
  const userEventType =
    asString(pluginConfig.orbitUserEventType) ?? parsed.ORBIT_USER_EVENT_TYPE.trim();
  const assistantEventType =
    asString(pluginConfig.orbitAssistantEventType) ??
    parsed.ORBIT_ASSISTANT_EVENT_TYPE.trim();

  return {
    orbitApiUrl: normalizeBaseUrl(apiUrl),
    orbitToken: token.trim(),
    memoryLimit,
    entityPrefix: entityPrefix || "openclaw",
    userEventType: userEventType || "user_prompt",
    assistantEventType: assistantEventType || "assistant_response",
    captureAssistantOutput:
      asBoolean(pluginConfig.orbitCaptureAssistantOutput) ??
      parseBoolean(parsed.ORBIT_CAPTURE_ASSISTANT_OUTPUT),
    preferSessionKey,
    identityLinks: mergeIdentityLinks(
      identityLinksFromRuntime,
      identityLinksFromEnv,
      identityLinksFromPlugin,
    ),
  };
}
