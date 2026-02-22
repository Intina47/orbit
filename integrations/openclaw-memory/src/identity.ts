import type { IdentityLinksMap } from "./config.js";
import type { HookContext, HookEvent } from "./types.js";

export interface ResolveEntityIdInput {
  event: HookEvent;
  context: HookContext;
  entityPrefix: string;
  preferSessionKey: boolean;
  identityLinks?: IdentityLinksMap;
}

const SESSION_KEY_PATHS: ReadonlyArray<ReadonlyArray<string>> = [
  ["sessionKey"],
  ["session", "key"],
  ["session", "id"],
  ["data", "sessionKey"],
  ["data", "session", "key"],
];

const CHANNEL_PATHS: ReadonlyArray<ReadonlyArray<string>> = [
  ["origin"],
  ["channel"],
  ["session", "origin"],
  ["session", "channel"],
  ["data", "origin"],
  ["data", "channel"],
];

const ID_PATHS: ReadonlyArray<ReadonlyArray<string>> = [
  ["entity_id"],
  ["entityId"],
  ["user_id"],
  ["userId"],
  ["peerId"],
  ["senderId"],
  ["normalizedPeerId"],
  ["conversation", "id"],
  ["thread", "id"],
  ["data", "entity_id"],
  ["data", "entityId"],
  ["data", "user_id"],
  ["data", "userId"],
  ["data", "peerId"],
  ["data", "senderId"],
  ["data", "normalizedPeerId"],
];

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

function normalizeIdentityKey(value: string): string {
  return value.trim().toLowerCase();
}

function sanitizeSegment(value: string): string {
  return value.trim().replace(/[^a-zA-Z0-9:_.@+\-]/g, "-");
}

function getFirstString(
  sources: ReadonlyArray<unknown>,
  paths: ReadonlyArray<ReadonlyArray<string>>,
): string | null {
  for (const source of sources) {
    for (const path of paths) {
      const value = readPath(source, path);
      if (typeof value === "string" && value.trim().length > 0) {
        return value.trim();
      }
    }
  }
  return null;
}

function listCandidateIds(
  sources: ReadonlyArray<unknown>,
  paths: ReadonlyArray<ReadonlyArray<string>>,
): string[] {
  const seen = new Set<string>();
  for (const source of sources) {
    for (const path of paths) {
      const value = readPath(source, path);
      if (typeof value === "string" && value.trim().length > 0) {
        seen.add(value.trim());
      }
    }
  }
  return [...seen];
}

function buildAliasIndex(identityLinks: IdentityLinksMap): Map<string, string> {
  const aliasIndex = new Map<string, string>();
  for (const [canonical, aliases] of Object.entries(identityLinks)) {
    const canonicalTrimmed = canonical.trim();
    if (canonicalTrimmed.length === 0) {
      continue;
    }
    aliasIndex.set(normalizeIdentityKey(canonicalTrimmed), canonicalTrimmed);
    for (const alias of aliases) {
      const normalizedAlias = normalizeIdentityKey(alias);
      if (normalizedAlias.length > 0) {
        aliasIndex.set(normalizedAlias, canonicalTrimmed);
      }
    }
  }
  return aliasIndex;
}

function resolveLinkedIdentity(
  rawIdentity: string,
  channel: string | null,
  aliasIndex: Map<string, string>,
): string | null {
  const candidates = new Set<string>([rawIdentity]);
  if (channel && !rawIdentity.includes(":")) {
    candidates.add(`${channel}:${rawIdentity}`);
  }
  for (const candidate of candidates) {
    const canonical = aliasIndex.get(normalizeIdentityKey(candidate));
    if (canonical) {
      return canonical;
    }
  }
  return null;
}

export function resolveEntityId(input: ResolveEntityIdInput): string {
  const sources: unknown[] = [input.event, input.context];
  const safePrefix = sanitizeSegment(input.entityPrefix || "openclaw");
  const aliasIndex = buildAliasIndex(input.identityLinks ?? {});

  const channel = getFirstString(sources, CHANNEL_PATHS);
  const sessionKey = getFirstString(sources, SESSION_KEY_PATHS);
  if (sessionKey) {
    const linked = resolveLinkedIdentity(sessionKey, channel, aliasIndex);
    if (linked) {
      return sanitizeSegment(linked);
    }
    if (input.preferSessionKey) {
      return sanitizeSegment(sessionKey);
    }
  }

  const candidateIds = listCandidateIds(sources, ID_PATHS);
  for (const candidateId of candidateIds) {
    const linked = resolveLinkedIdentity(candidateId, channel, aliasIndex);
    if (linked) {
      return sanitizeSegment(linked);
    }
  }

  if (candidateIds.length > 0) {
    const firstCandidate = candidateIds[0];
    if (!firstCandidate) {
      return `${safePrefix}:anonymous`;
    }
    const primaryId = sanitizeSegment(firstCandidate);
    if (channel && !primaryId.includes(":")) {
      return `${safePrefix}:${sanitizeSegment(channel)}:${primaryId}`;
    }
    return `${safePrefix}:${primaryId}`;
  }

  return `${safePrefix}:anonymous`;
}
