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

export type OrbitDashboardSessionResponse = {
  authenticated: boolean
  mode: "password" | "oidc" | "disabled"
  subject?: string
  email?: string
  name?: string
  provider?: "password" | "oidc" | "disabled"
  oidc_login_path?: string
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

  constructor(status: number, detail: string) {
    super(detail)
    this.status = status
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
      throw new OrbitDashboardApiError(
        response.status,
        extractErrorDetail(parsedBody, bodyText, response.status),
      )
    }
    return parsedBody as T
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

function extractErrorDetail(parsedBody: unknown, fallbackText: string, status: number): string {
  if (typeof parsedBody === "object" && parsedBody !== null && "detail" in parsedBody) {
    const detail = (parsedBody as { detail?: unknown }).detail
    if (typeof detail === "string" && detail.trim()) {
      return detail
    }
  }
  if (fallbackText.trim()) {
    return fallbackText.trim()
  }
  return `Request failed with status ${status}.`
}
