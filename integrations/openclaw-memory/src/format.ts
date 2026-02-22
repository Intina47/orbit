import type { OrbitMemory } from "./orbit-client.js";

function compactContent(value: string, maxLength: number): string {
  const compact = value.replace(/\s+/g, " ").trim();
  if (compact.length <= maxLength) {
    return compact;
  }
  return `${compact.slice(0, maxLength)}...`;
}

export function formatRetrievedMemories(memories: OrbitMemory[]): string {
  if (memories.length === 0) {
    return "";
  }
  const lines = memories.map((memory, index) => {
    const prefix = memory.event_type ? `[${memory.event_type}] ` : "";
    return `${index + 1}. ${prefix}${compactContent(memory.content, 280)}`;
  });
  return [
    "Orbit memory context (already ranked):",
    ...lines,
    "Use only the items relevant to the current request.",
  ].join("\n");
}
