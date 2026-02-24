import { NextRequest } from "next/server"

import { enforceDashboardOrigin, requireDashboardSession } from "@/lib/dashboard-auth"
import { badRequestResponse, proxyDashboardRequest } from "@/lib/orbit-dashboard-proxy"

export const runtime = "nodejs"
export const dynamic = "force-dynamic"

type RouteContext = {
  params: Promise<{ keyId: string }>
}

export async function POST(
  request: NextRequest,
  context: RouteContext,
) {
  const originFailure = enforceDashboardOrigin(request)
  if (originFailure) {
    return originFailure
  }

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

  const { keyId } = await context.params
  return proxyDashboardRequest({
    request,
    path: `/v1/dashboard/keys/${encodeURIComponent(keyId)}/rotate`,
    method: "POST",
    body,
    requiredScopes: ["keys:write"],
    auditAction: "rotate_key",
  })
}
