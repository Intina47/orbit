export type OrbitApiKeySummary = {
  key_id: string
  name: string
  key_prefix: string
  scopes: string[]
  status: string
  created_at: string
  last_used_at: string | null
  last_used_source: string | null
  revoked_at: string | null
}

export type OrbitApiKeyIssueResponse = OrbitApiKeySummary & {
  key: string
}

export type OrbitApiKeyListResponse = {
  data: OrbitApiKeySummary[]
  cursor: string | null
  has_more: boolean
}

export type OrbitApiKeyRevokeResponse = {
  key_id: string
  revoked: boolean
  revoked_at: string | null
}

export type OrbitApiKeyRotateResponse = {
  revoked_key_id: string
  new_key: OrbitApiKeyIssueResponse
}

export type OrbitApiKeyCreateRequest = {
  name: string
  scopes: string[]
}

export type OrbitApiKeyRotateRequest = {
  name?: string
  scopes?: string[]
}

export type OrbitAccountQuota = {
  events_per_day: number
  queries_per_day: number
  events_per_month?: number | null
  queries_per_month?: number | null
  api_keys?: number | null
  retention_days?: number | null
  plan?: string | null
  reset_at?: string | null
  warning_threshold_percent?: number | null
  critical_threshold_percent?: number | null
}

export type OrbitPilotProRequest = {
  requested: boolean
  status: string
  requested_at?: string | null
  requested_by_email?: string | null
  requested_by_name?: string | null
  email_sent_at?: string | null
}

export type OrbitMetadataSummary = {
  total_inferred_facts: number
  confirmed_facts: number
  contested_facts: number
  conflict_guards: number
  contested_ratio: number
  conflict_guard_ratio: number
  average_fact_age_days: number
}

export type OrbitTenantUsageMetric = {
  used: number
  limit?: number | null
  remaining?: number | null
  utilization_percent: number
  status: "ok" | "warning" | "critical" | "limit"
}

export type OrbitTenantMetricsResponse = {
  generated_at: string
  plan: string
  reset_at: string
  warning_threshold_percent: number
  critical_threshold_percent: number
  ingest: OrbitTenantUsageMetric
  retrieve: OrbitTenantUsageMetric
  api_keys: OrbitTenantUsageMetric
  storage_usage_mb: number
  pilot_pro_requested: boolean
  pilot_pro_requested_at?: string | null
}

export type OrbitStatusResponse = {
  connected: boolean
  api_version: string
  account_usage: {
    events_ingested_this_month: number
    queries_this_month: number
    storage_usage_mb: number
    active_api_keys?: number | null
    quota: OrbitAccountQuota
  }
  pilot_pro_request?: OrbitPilotProRequest | null
  latest_ingestion?: string | null
  uptime_percent: number
  metadata_summary: OrbitMetadataSummary
}

export type OrbitPilotProRequestResponse = {
  request: OrbitPilotProRequest
  created: boolean
  email_sent: boolean
}

export type OrbitDashboardSessionResponse = {
  authenticated: boolean
  mode: "password" | "oidc" | "disabled"
  subject?: string
  email?: string
  name?: string
  provider?: "password" | "oidc" | "disabled"
  auth_provider?: string
  picture?: string
  oidc_login_path?: string
  oidc_login_providers?: Array<{
    id: string
    label: string
    path: string
  }>
}

const DEFAULT_PROXY_PREFIX = "/api/dashboard"
const DEFAULT_ORBIT_API_BASE_URL = "http://localhost:8000"

export const DASHBOARD_SCOPE_OPTIONS = [
  "read",
  "write",
  "feedback",
  "keys:read",
  "keys:write",
] as const

export const DASHBOARD_DEFAULT_SCOPES: string[] = ["read", "write", "feedback"]

export class OrbitDashboardApiError extends Error {
  status: number
  code: string | null

  constructor(status: number, detail: string, code: string | null = null) {
    super(detail)
    this.status = status
    this.code = code
  }
}

export function getOrbitApiBaseUrl(): string {
  const raw = process.env.NEXT_PUBLIC_ORBIT_API_BASE_URL?.trim()
  if (!raw) {
    return DEFAULT_ORBIT_API_BASE_URL
  }
  return raw.replace(/\/+$/, "")
}

export class OrbitDashboardClient {
  private readonly proxyPrefix: string

  constructor(proxyPrefix: string = DEFAULT_PROXY_PREFIX) {
    this.proxyPrefix = proxyPrefix.replace(/\/+$/, "")
  }

  async getSession(): Promise<OrbitDashboardSessionResponse> {
    return this.request<OrbitDashboardSessionResponse>(`${this.proxyPrefix}/auth/session`)
  }

  async login(password: string): Promise<OrbitDashboardSessionResponse> {
    return this.request<OrbitDashboardSessionResponse>(`${this.proxyPrefix}/auth/login`, {
      method: "POST",
      body: JSON.stringify({ password }),
    })
  }

  async logout(): Promise<OrbitDashboardSessionResponse> {
    return this.request<OrbitDashboardSessionResponse>(`${this.proxyPrefix}/auth/logout`, {
      method: "POST",
    })
  }

  async listApiKeys(options?: {
    limit?: number
    cursor?: string | null
  }): Promise<OrbitApiKeyListResponse> {
    const query = new URLSearchParams()
    if (options?.limit !== undefined) {
      query.set("limit", String(options.limit))
    }
    if (options?.cursor) {
      query.set("cursor", options.cursor)
    }
    const suffix = query.size > 0 ? `?${query.toString()}` : ""
    return this.request<OrbitApiKeyListResponse>(`${this.proxyPrefix}/keys${suffix}`)
  }

  async getStatus(): Promise<OrbitStatusResponse> {
    return this.request<OrbitStatusResponse>(`${this.proxyPrefix}/status`)
  }

  async requestPilotPro(): Promise<OrbitPilotProRequestResponse> {
    return this.request<OrbitPilotProRequestResponse>(`${this.proxyPrefix}/pilot-pro/request`, {
      method: "POST",
    })
  }

  async getMetricsText(): Promise<string> {
    return this.requestText(`${this.proxyPrefix}/metrics`)
  }

  async getTenantMetrics(): Promise<OrbitTenantMetricsResponse> {
    return this.request<OrbitTenantMetricsResponse>(`${this.proxyPrefix}/tenant-metrics`)
  }

  async createApiKey(payload: OrbitApiKeyCreateRequest): Promise<OrbitApiKeyIssueResponse> {
    return this.request<OrbitApiKeyIssueResponse>(`${this.proxyPrefix}/keys`, {
      method: "POST",
      body: JSON.stringify(payload),
    })
  }

  async revokeApiKey(keyId: string): Promise<OrbitApiKeyRevokeResponse> {
    return this.request<OrbitApiKeyRevokeResponse>(`${this.proxyPrefix}/keys/${encodeURIComponent(keyId)}/revoke`, {
      method: "POST",
    })
  }

  async rotateApiKey(
    keyId: string,
    payload: OrbitApiKeyRotateRequest,
  ): Promise<OrbitApiKeyRotateResponse> {
    return this.request<OrbitApiKeyRotateResponse>(`${this.proxyPrefix}/keys/${encodeURIComponent(keyId)}/rotate`, {
      method: "POST",
      body: JSON.stringify(payload),
    })
  }

  private async request<T>(
    path: string,
    init?: RequestInit,
  ): Promise<T> {
    const headers = new Headers(init?.headers)
    headers.set("Accept", "application/json")
    if (init?.body) {
      headers.set("Content-Type", "application/json")
    }
    const response = await fetch(path, {
      ...init,
      headers,
      cache: "no-store",
    })
    const bodyText = await response.text()
    const parsedBody = parseBody(bodyText)
    if (!response.ok) {
      const resolvedError = extractError(parsedBody, bodyText, response.status)
      throw new OrbitDashboardApiError(
        response.status,
        resolvedError.message,
        resolvedError.code,
      )
    }
    return parsedBody as T
  }

  private async requestText(path: string, init?: RequestInit): Promise<string> {
    const headers = new Headers(init?.headers)
    headers.set("Accept", "text/plain, application/json")
    const response = await fetch(path, {
      ...init,
      headers,
      cache: "no-store",
    })
    const bodyText = await response.text()
    if (!response.ok) {
      const parsedBody = parseBody(bodyText)
      const resolvedError = extractError(parsedBody, bodyText, response.status)
      throw new OrbitDashboardApiError(
        response.status,
        resolvedError.message,
        resolvedError.code,
      )
    }
    return bodyText
  }
}

function parseBody(text: string): unknown {
  if (!text.trim()) {
    return {}
  }
  try {
    return JSON.parse(text)
  } catch {
    return {}
  }
}

function extractError(
  parsedBody: unknown,
  fallbackText: string,
  status: number,
): { message: string; code: string | null } {
  if (typeof parsedBody === "object" && parsedBody !== null) {
    const detail = (parsedBody as { detail?: unknown }).detail
    const topLevelCode = normalizeErrorCode(
      (parsedBody as { error_code?: unknown }).error_code,
    )
    if (typeof detail === "string" && detail.trim()) {
      return { message: detail.trim(), code: topLevelCode }
    }
    if (typeof detail === "object" && detail !== null) {
      const detailObj = detail as { message?: unknown; error_code?: unknown }
      const message = detailObj.message
      if (typeof message === "string" && message.trim()) {
        return {
          message: message.trim(),
          code: normalizeErrorCode(detailObj.error_code) ?? topLevelCode,
        }
      }
    }
  }
  if (fallbackText.trim()) {
    return { message: fallbackText.trim(), code: null }
  }
  return { message: `Request failed with status ${status}.`, code: null }
}

function normalizeErrorCode(value: unknown): string | null {
  if (typeof value !== "string") {
    return null
  }
  const normalized = value.trim()
  return normalized.length > 0 ? normalized : null
}
