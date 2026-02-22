import type { OrbitPluginConfig } from "./config.js";

export interface OrbitMemory {
  memory_id: string;
  content: string;
  event_type?: string;
  score?: number;
  created_at?: string;
}

export interface IngestInput {
  content: string;
  entityId: string;
  eventType: string;
  metadata?: Record<string, unknown>;
}

export interface RetrieveInput {
  query: string;
  entityId: string;
  limit: number;
  eventType?: string;
}

export interface FeedbackInput {
  memoryId: string;
  helpful: boolean;
  outcomeValue?: number;
}

type Logger = (...args: unknown[]) => void;

function truncate(value: string, maxLength: number): string {
  if (value.length <= maxLength) {
    return value;
  }
  return `${value.slice(0, maxLength)}...`;
}

function toMemory(value: unknown): OrbitMemory | null {
  if (typeof value !== "object" || value === null) {
    return null;
  }
  const record = value as Record<string, unknown>;
  if (typeof record.memory_id !== "string" || typeof record.content !== "string") {
    return null;
  }
  const memory: OrbitMemory = {
    memory_id: record.memory_id,
    content: record.content,
  };
  if (typeof record.event_type === "string") {
    memory.event_type = record.event_type;
  }
  if (typeof record.score === "number") {
    memory.score = record.score;
  }
  if (typeof record.created_at === "string") {
    memory.created_at = record.created_at;
  }
  return memory;
}

export class OrbitClient {
  private missingTokenLogged = false;

  public constructor(
    private readonly config: OrbitPluginConfig,
    private readonly log: Logger,
  ) {}

  public async ingest(input: IngestInput): Promise<void> {
    if (!this.isEnabled("ingest")) {
      return;
    }
    const payload: Record<string, unknown> = {
      content: input.content,
      entity_id: input.entityId,
      event_type: input.eventType,
    };
    if (input.metadata) {
      payload.metadata = input.metadata;
    }
    await this.request("POST", "/v1/ingest", payload);
  }

  public async retrieve(input: RetrieveInput): Promise<OrbitMemory[]> {
    if (!this.isEnabled("retrieve")) {
      return [];
    }
    const params = new URLSearchParams({
      query: input.query,
      entity_id: input.entityId,
      limit: String(input.limit),
    });
    if (input.eventType) {
      params.set("event_type", input.eventType);
    }
    const data = await this.request("GET", `/v1/retrieve?${params.toString()}`);
    const records = (data as Record<string, unknown>).memories;
    if (!Array.isArray(records)) {
      return [];
    }
    return records
      .map((record) => toMemory(record))
      .filter((record): record is OrbitMemory => record !== null);
  }

  public async feedback(input: FeedbackInput): Promise<void> {
    if (!this.isEnabled("feedback")) {
      return;
    }
    const payload: Record<string, unknown> = {
      memory_id: input.memoryId,
      helpful: input.helpful,
    };
    if (typeof input.outcomeValue === "number") {
      payload.outcome_value = input.outcomeValue;
    }
    await this.request("POST", "/v1/feedback", payload);
  }

  public async status(): Promise<Record<string, unknown>> {
    if (!this.isEnabled("status")) {
      return { enabled: false, reason: "missing ORBIT_JWT_TOKEN" };
    }
    const data = await this.request("GET", "/v1/status");
    if (typeof data === "object" && data !== null) {
      return data as Record<string, unknown>;
    }
    return { enabled: true, data };
  }

  private isEnabled(operation: string): boolean {
    if (this.config.orbitToken.length > 0) {
      return true;
    }
    if (!this.missingTokenLogged) {
      this.log(
        `[orbit] ${operation}: ORBIT_JWT_TOKEN not set, Orbit calls are disabled.`,
      );
      this.missingTokenLogged = true;
    }
    return false;
  }

  private async request(
    method: "GET" | "POST",
    path: string,
    body?: Record<string, unknown>,
  ): Promise<unknown> {
    const url = `${this.config.orbitApiUrl}${path}`;
    const headers: Record<string, string> = {
      Authorization: `Bearer ${this.config.orbitToken}`,
      Accept: "application/json",
    };
    const init: RequestInit = { method, headers };
    if (body) {
      headers["Content-Type"] = "application/json";
      init.body = JSON.stringify(body);
    }

    const response = await fetch(url, init);
    if (!response.ok) {
      const text = await response.text();
      throw new Error(
        `[orbit] ${method} ${path} failed (${response.status}): ${truncate(text, 220)}`,
      );
    }

    if (response.status === 204) {
      return {};
    }
    const contentType = response.headers.get("content-type") ?? "";
    if (contentType.includes("application/json")) {
      return await response.json();
    }
    return { raw: await response.text() };
  }
}
