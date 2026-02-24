import { NextRequest } from "next/server"

import { enforceDashboardOrigin, requireDashboardSession } from "@/lib/dashboard-auth"
import { proxyDashboardRequest } from "@/lib/orbit-dashboard-proxy"

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

  const { keyId } = await context.params
  return proxyDashboardRequest({
    request,
    path: `/v1/dashboard/keys/${encodeURIComponent(keyId)}/revoke`,
    method: "POST",
    requiredScopes: ["keys:write"],
    auditAction: "revoke_key",
  })
}
