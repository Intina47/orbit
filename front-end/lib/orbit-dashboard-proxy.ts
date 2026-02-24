import { NextResponse } from "next/server"

const DEFAULT_TARGET_URL = "http://localhost:8000"
const FORWARDED_HEADERS = [
  "x-ratelimit-limit",
  "x-ratelimit-remaining",
  "x-ratelimit-reset",
  "retry-after",
  "x-idempotency-replayed",
] as const

type ProxyMethod = "GET" | "POST"

type ProxyRequestOptions = {
  path: string
  method: ProxyMethod
  body?: string
}

export async function proxyDashboardRequest(
  options: ProxyRequestOptions,
): Promise<NextResponse> {
  const targetUrl = resolveTargetUrl()
  const bearerToken = resolveBearerToken()
  if (!bearerToken) {
    return NextResponse.json(
      {
        detail:
          "Dashboard proxy is missing ORBIT_DASHBOARD_SERVER_BEARER_TOKEN on the server.",
      },
      { status: 500 },
    )
  }

  const headers = new Headers()
  headers.set("Authorization", `Bearer ${bearerToken}`)
  headers.set("Accept", "application/json")
  if (options.body !== undefined) {
    headers.set("Content-Type", "application/json")
  }

  const upstream = await fetch(`${targetUrl}${options.path}`, {
    method: options.method,
    headers,
    body: options.body,
    cache: "no-store",
  })

  const responseBody = await upstream.text()
  const response = new NextResponse(responseBody, {
    status: upstream.status,
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
  response.headers.set("Cache-Control", "no-store")
  return response
}

export function badRequestResponse(detail: string): NextResponse {
  return NextResponse.json({ detail }, { status: 400, headers: { "Cache-Control": "no-store" } })
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

function resolveBearerToken(): string {
  return process.env.ORBIT_DASHBOARD_SERVER_BEARER_TOKEN?.trim() ?? ""
}
