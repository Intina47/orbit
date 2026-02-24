import { NextRequest } from "next/server"

import { requireDashboardSession } from "@/lib/dashboard-auth"
import { badRequestResponse, proxyDashboardRequest } from "@/lib/orbit-dashboard-proxy"

export const runtime = "nodejs"
export const dynamic = "force-dynamic"

export async function GET(request: NextRequest) {
  const authFailure = requireDashboardSession(request)
  if (authFailure) {
    return authFailure
  }

  const url = new URL(request.url)
  const query = url.searchParams.toString()
  const path = query ? `/v1/dashboard/keys?${query}` : "/v1/dashboard/keys"
  return proxyDashboardRequest({
    path,
    method: "GET",
  })
}

export async function POST(request: NextRequest) {
  const authFailure = requireDashboardSession(request)
  if (authFailure) {
    return authFailure
  }

  let body = ""
  try {
    body = JSON.stringify(await request.json())
  } catch {
    return badRequestResponse("Request body must be valid JSON.")
  }
  return proxyDashboardRequest({
    path: "/v1/dashboard/keys",
    method: "POST",
    body,
  })
}
