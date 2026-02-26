import { NextRequest } from "next/server"

import { requireDashboardSession } from "@/lib/dashboard-auth"
import { proxyDashboardRequest } from "@/lib/orbit-dashboard-proxy"

export const runtime = "nodejs"
export const dynamic = "force-dynamic"

export async function GET(request: NextRequest) {
  const authFailure = requireDashboardSession(request)
  if (authFailure) {
    return authFailure
  }

  return proxyDashboardRequest({
    request,
    path: "/v1/dashboard/memory-quality",
    method: "GET",
    requiredScopes: ["keys:read", "read"],
    auditAction: "memory_quality",
  })
}
