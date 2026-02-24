import { NextRequest, NextResponse } from "next/server"

import {
  DASHBOARD_SESSION_COOKIE_NAME,
  clearDashboardLoginFailures,
  createDashboardSessionToken,
  dashboardLoginConfigError,
  enforceDashboardOrigin,
  ensureDashboardLoginAllowed,
  getDashboardAuthMode,
  getDashboardSessionCookieOptions,
  logDashboardAuthEvent,
  recordDashboardLoginFailure,
  verifyDashboardPassword,
} from "@/lib/dashboard-auth"
import { badRequestResponse } from "@/lib/orbit-dashboard-proxy"

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
  if (authMode === "disabled") {
    logDashboardAuthEvent("dashboard_login_disabled_mode", request)
    return NextResponse.json(
      { authenticated: true, mode: authMode, subject: "dashboard-disabled", provider: "disabled" },
      { status: 200, headers: NO_STORE_HEADERS },
    )
  }
  if (authMode === "oidc") {
    return badRequestResponse("OIDC mode is enabled. Start login at /api/dashboard/auth/oidc/start.")
  }

  const configError = dashboardLoginConfigError()
  if (configError) {
    return NextResponse.json({ detail: configError }, { status: 500, headers: NO_STORE_HEADERS })
  }

  const throttleFailure = ensureDashboardLoginAllowed(request)
  if (throttleFailure) {
    return throttleFailure
  }

  let payload: unknown
  try {
    payload = await request.json()
  } catch {
    return badRequestResponse("Request body must be valid JSON.")
  }

  const passwordValue = extractPassword(payload)
  if (passwordValue === null) {
    return badRequestResponse("Request body must include a non-empty password.")
  }

  if (!verifyDashboardPassword(passwordValue)) {
    recordDashboardLoginFailure(request)
    logDashboardAuthEvent("dashboard_login_failure", request)
    return NextResponse.json(
      { detail: "Invalid dashboard credentials." },
      { status: 401, headers: NO_STORE_HEADERS },
    )
  }

  clearDashboardLoginFailures(request)
  const response = NextResponse.json(
    { authenticated: true, mode: authMode, subject: "dashboard-user", provider: "password" },
    { status: 200, headers: NO_STORE_HEADERS },
  )
  response.cookies.set(
    DASHBOARD_SESSION_COOKIE_NAME,
    createDashboardSessionToken({
      subject: "dashboard-user",
      issuer: "orbit-dashboard-password",
      provider: "password",
    }),
    getDashboardSessionCookieOptions(),
  )
  logDashboardAuthEvent("dashboard_login_success", request)
  return response
}

function extractPassword(payload: unknown): string | null {
  if (typeof payload !== "object" || payload === null || !("password" in payload)) {
    return null
  }
  const rawPassword = (payload as { password?: unknown }).password
  if (typeof rawPassword !== "string") {
    return null
  }
  const normalized = rawPassword.trim()
  if (!normalized) {
    return null
  }
  return normalized
}
