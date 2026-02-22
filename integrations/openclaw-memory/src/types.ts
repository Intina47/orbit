export type JsonObject = Record<string, unknown>;

export interface OpenClawToolHandler {
  (args: JsonObject): Promise<unknown> | unknown;
}

export interface OpenClawLogger {
  info?: (...args: unknown[]) => void;
  warn?: (...args: unknown[]) => void;
  error?: (...args: unknown[]) => void;
  debug?: (...args: unknown[]) => void;
}

export type HookEvent = JsonObject;
export type HookContext = JsonObject;

export type HookCallback =
  (event: HookEvent, context: HookContext) => Promise<HookEvent | void> | HookEvent | void;

export interface OpenClawCommandDefinition {
  name: string;
  description?: string;
  execute: (args: string, context?: HookContext) => Promise<string> | string;
}

export interface OpenClawToolDefinition {
  name: string;
  description: string;
  inputSchema: JsonObject;
  execute: OpenClawToolHandler;
}

export interface OpenClawToolRegistrationOptions {
  requiresAuth?: boolean;
}

export interface OpenClawPluginApi {
  log: (...args: unknown[]) => void;
  logger?: OpenClawLogger;
  config?: JsonObject;
  pluginConfig?: JsonObject;
  registerCommand?: (
    definitionOrName: OpenClawCommandDefinition | string,
    legacyHandler?: (args: string, context?: HookContext) => Promise<string> | string,
  ) => void;
  registerTool?: (
    definitionOrName: OpenClawToolDefinition | string,
    descriptionOrOptions?: string | OpenClawToolRegistrationOptions,
    legacyInputSchema?: JsonObject,
    legacyHandler?: OpenClawToolHandler,
  ) => void;
  registerHook?: (
    event: string,
    handler: ((context: HookContext) => Promise<HookContext | void> | HookContext | void) | HookCallback,
  ) => void;
  on?: (event: string, handler: HookCallback) => void;
}

export interface OpenClawPlugin {
  id: string;
  kind: "memory" | "integration" | "tooling" | "safety" | string;
  name: string;
  version: string;
  description?: string;
  configSchema?: JsonObject;
  slots?: JsonObject;
  register?: (api: OpenClawPluginApi) => Promise<void> | void;
  init?: (api: OpenClawPluginApi) => Promise<void> | void;
}
