import { NextRequest, NextResponse } from "next/server"

import {
  DASHBOARD_SESSION_COOKIE_NAME,
  getDashboardAuthMode,
  getDashboardSessionClearCookieOptions,
} from "@/lib/dashboard-auth"

export const runtime = "nodejs"
export const dynamic = "force-dynamic"

const NO_STORE_HEADERS = {
  "Cache-Control": "no-store",
}

export async function POST(_request: NextRequest) {
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
  return response
}
