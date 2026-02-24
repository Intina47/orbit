import { NextRequest, NextResponse } from "next/server"

import {
  DASHBOARD_OIDC_NONCE_COOKIE_NAME,
  DASHBOARD_OIDC_STATE_COOKIE_NAME,
  DASHBOARD_OIDC_VERIFIER_COOKIE_NAME,
  buildOidcAuthorizationRequest,
  dashboardLoginConfigError,
  getDashboardAuthMode,
  getDashboardOidcTransientCookieOptions,
  logDashboardAuthEvent,
} from "@/lib/dashboard-auth"

export const runtime = "nodejs"
export const dynamic = "force-dynamic"

export async function GET(request: NextRequest) {
  const mode = getDashboardAuthMode()
  if (mode !== "oidc") {
    return NextResponse.json(
      { detail: "OIDC login route is available only when ORBIT_DASHBOARD_AUTH_MODE=oidc." },
      { status: 400, headers: { "Cache-Control": "no-store" } },
    )
  }

  const configError = dashboardLoginConfigError()
  if (configError) {
    return NextResponse.json(
      { detail: configError },
      { status: 500, headers: { "Cache-Control": "no-store" } },
    )
  }

  try {
    const authorization = await buildOidcAuthorizationRequest(request)
    const response = NextResponse.redirect(authorization.authorizationUrl, {
      status: 307,
      headers: { "Cache-Control": "no-store" },
    })
    const cookieOptions = getDashboardOidcTransientCookieOptions()
    response.cookies.set(
      DASHBOARD_OIDC_STATE_COOKIE_NAME,
      authorization.state,
      cookieOptions,
    )
    response.cookies.set(
      DASHBOARD_OIDC_VERIFIER_COOKIE_NAME,
      authorization.codeVerifier,
      cookieOptions,
    )
    response.cookies.set(
      DASHBOARD_OIDC_NONCE_COOKIE_NAME,
      authorization.nonce,
      cookieOptions,
    )
    logDashboardAuthEvent("dashboard_oidc_start", request)
    return response
  } catch (error) {
    logDashboardAuthEvent("dashboard_oidc_start_failed", request, {
      detail: error instanceof Error ? error.message : String(error),
    })
    return NextResponse.json(
      { detail: error instanceof Error ? error.message : "Failed to start OIDC login." },
      { status: 500, headers: { "Cache-Control": "no-store" } },
    )
  }
}
