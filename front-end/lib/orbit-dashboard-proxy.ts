import type { NextRequest } from "next/server"
import { NextResponse } from "next/server"

import { logDashboardAuthEvent, resolveProxyBearerToken } from "@/lib/dashboard-auth"

const DEFAULT_TARGET_URL = "http://localhost:8000"
const FORWARDED_HEADERS = [
  "x-ratelimit-limit",
  "x-ratelimit-remaining",
  "x-ratelimit-reset",
  "retry-after",
  "x-idempotency-replayed",
  "x-orbit-error-code",
] as const

const NO_STORE_HEADERS = {
  "Cache-Control": "no-store",
}

type ProxyMethod = "GET" | "POST"

type ProxyRequestOptions = {
  request: NextRequest
  path: string
  method: ProxyMethod
  body?: string
  acceptHeader?: string
  requiredScopes?: readonly string[]
  auditAction?: string
}

export async function proxyDashboardRequest(
  options: ProxyRequestOptions,
): Promise<NextResponse> {
  const targetUrl = resolveTargetUrl()
  const authResolution = resolveProxyBearerToken(
    options.request,
    options.requiredScopes ?? [],
  )
  if (!authResolution.ok) {
    return NextResponse.json(
      { detail: authResolution.detail },
      {
        status: authResolution.status,
        headers: NO_STORE_HEADERS,
      },
    )
  }

  const headers = new Headers()
  headers.set("Authorization", `Bearer ${authResolution.token}`)
  headers.set("Accept", options.acceptHeader ?? "application/json")
  headers.set("X-Orbit-Proxy-Source", "dashboard-web")
  if (options.body !== undefined) {
    headers.set("Content-Type", "application/json")
  }

  let upstream: Response
  try {
    upstream = await fetch(`${targetUrl}${options.path}`, {
      method: options.method,
      headers,
      body: options.body,
      cache: "no-store",
    })
  } catch (error) {
    const safeTarget = targetUrl.replace(/\/+$/, "")
    const detail =
      process.env.NODE_ENV === "production"
        ? "Orbit API is unreachable from dashboard proxy."
        : `Orbit API is unreachable from dashboard proxy (target: ${safeTarget}).`
    logDashboardAuthEvent("dashboard_proxy_upstream_unreachable", options.request, {
      target: `${targetUrl}${options.path}`,
      detail: error instanceof Error ? error.message : String(error),
    })
    return NextResponse.json(
      {
        detail: {
          message: detail,
          error_code: "dashboard_proxy_upstream_unreachable",
        },
      },
      { status: 502, headers: NO_STORE_HEADERS },
    )
  }

  const responseBody = await upstream.text()
  const response = new NextResponse(responseBody, {
    status: upstream.status,
    headers: NO_STORE_HEADERS,
  })
  const contentType = upstream.headers.get("content-type")
  if (contentType) {
    response.headers.set("Content-Type", contentType)
  } else {
    response.headers.set("Content-Type", "application/json; charset=utf-8")
  }
  for (const header of FORWARDED_HEADERS) {
    const value = upstream.headers.get(header)
    if (value) {
      response.headers.set(header, value)
    }
  }

  const resolvedAction = options.auditAction?.trim()
  if (resolvedAction) {
    logDashboardAuthEvent(
      `dashboard_proxy_${resolvedAction}`,
      options.request,
      {
        account_key: authResolution.accountKey,
        subject: authResolution.principal.subject,
        status_code: upstream.status,
      },
    )
  }

  return response
}

export function badRequestResponse(detail: string): NextResponse {
  return NextResponse.json({ detail }, { status: 400, headers: NO_STORE_HEADERS })
}

function resolveTargetUrl(): string {
  const serverOverride = process.env.ORBIT_DASHBOARD_PROXY_BASE_URL?.trim()
  if (serverOverride) {
    return serverOverride.replace(/\/+$/, "")
  }
  const publicConfigured = process.env.NEXT_PUBLIC_ORBIT_API_BASE_URL?.trim()
  if (publicConfigured) {
    return publicConfigured.replace(/\/+$/, "")
  }
  return DEFAULT_TARGET_URL
}
