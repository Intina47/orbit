import { NextRequest } from "next/server"

import { requireDashboardSession } from "@/lib/dashboard-auth"
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
  const authFailure = requireDashboardSession(request)
  if (authFailure) {
    return authFailure
  }

  const { keyId } = await context.params
  return proxyDashboardRequest({
    path: `/v1/dashboard/keys/${encodeURIComponent(keyId)}/revoke`,
    method: "POST",
  })
}
