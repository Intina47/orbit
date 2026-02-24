import { NextRequest, NextResponse } from "next/server"

import {
  DASHBOARD_SESSION_COOKIE_NAME,
  enforceDashboardOrigin,
  getDashboardAuthMode,
  getDashboardSessionClearCookieOptions,
  logDashboardAuthEvent,
} from "@/lib/dashboard-auth"

export const runtime = "nodejs"
export const dynamic = "force-dynamic"

const NO_STORE_HEADERS = {
  "Cache-Control": "no-store",
}

export async function POST(request: NextRequest) {
  const originFailure = enforceDashboardOrigin(request)
  if (originFailure) {
    return originFailure
  }

  const authMode = getDashboardAuthMode()
  const response = NextResponse.json(
    { authenticated: authMode === "disabled", mode: authMode },
    { status: 200, headers: NO_STORE_HEADERS },
  )
  response.cookies.set(
    DASHBOARD_SESSION_COOKIE_NAME,
    "",
    getDashboardSessionClearCookieOptions(),
  )
  logDashboardAuthEvent("dashboard_logout", request)
  return response
}
