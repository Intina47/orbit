import { NextRequest } from "next/server"

import { enforceDashboardOrigin, requireDashboardSession } from "@/lib/dashboard-auth"
import { proxyDashboardRequest } from "@/lib/orbit-dashboard-proxy"

export const runtime = "nodejs"
export const dynamic = "force-dynamic"

export async function POST(request: NextRequest) {
  const originFailure = enforceDashboardOrigin(request)
  if (originFailure) {
    return originFailure
  }

  const authFailure = requireDashboardSession(request)
  if (authFailure) {
    return authFailure
  }

  return proxyDashboardRequest({
    request,
    path: "/v1/dashboard/pilot-pro/request",
    method: "POST",
    requiredScopes: ["keys:write"],
    auditAction: "pilot_pro_request",
  })
}
