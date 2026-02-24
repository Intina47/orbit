import { NextRequest, NextResponse } from "next/server"

import {
  DASHBOARD_OIDC_NONCE_COOKIE_NAME,
  DASHBOARD_OIDC_STATE_COOKIE_NAME,
  DASHBOARD_OIDC_VERIFIER_COOKIE_NAME,
  DASHBOARD_SESSION_COOKIE_NAME,
  createDashboardSessionToken,
  exchangeOidcCodeForPrincipal,
  getDashboardAuthMode,
  getDashboardOidcClearCookieOptions,
  getDashboardSessionCookieOptions,
  logDashboardAuthEvent,
} from "@/lib/dashboard-auth"

export const runtime = "nodejs"
export const dynamic = "force-dynamic"

export async function GET(request: NextRequest) {
  const mode = getDashboardAuthMode()
  if (mode !== "oidc") {
    return NextResponse.redirect(new URL("/dashboard?auth_error=oidc_disabled", request.url), {
      status: 307,
      headers: { "Cache-Control": "no-store" },
    })
  }

  const callbackUrl = new URL(request.url)
  const upstreamError = callbackUrl.searchParams.get("error")?.trim()
  if (upstreamError) {
    logDashboardAuthEvent("dashboard_oidc_callback_error", request, { error: upstreamError })
    return redirectToDashboard(request, "oidc_provider_error")
  }

  const returnedState = callbackUrl.searchParams.get("state")?.trim() ?? ""
  const code = callbackUrl.searchParams.get("code")?.trim() ?? ""
  const expectedState = request.cookies.get(DASHBOARD_OIDC_STATE_COOKIE_NAME)?.value?.trim() ?? ""
  const codeVerifier = request.cookies.get(DASHBOARD_OIDC_VERIFIER_COOKIE_NAME)?.value?.trim() ?? ""
  if (!returnedState || !expectedState || returnedState !== expectedState || !code || !codeVerifier) {
    logDashboardAuthEvent("dashboard_oidc_callback_state_invalid", request)
    return redirectToDashboard(request, "oidc_state_invalid")
  }

  try {
    const principal = await exchangeOidcCodeForPrincipal({
      request,
      code,
      codeVerifier,
    })
    const response = NextResponse.redirect(new URL("/dashboard", request.url), {
      status: 307,
      headers: { "Cache-Control": "no-store" },
    })
    response.cookies.set(
      DASHBOARD_SESSION_COOKIE_NAME,
      createDashboardSessionToken(principal),
      getDashboardSessionCookieOptions(),
    )
    clearOidcTransientCookies(response)
    logDashboardAuthEvent("dashboard_oidc_callback_success", request, {
      issuer: principal.issuer,
      subject: principal.subject,
      tenant: principal.tenant,
    })
    return response
  } catch (error) {
    logDashboardAuthEvent("dashboard_oidc_callback_failed", request, {
      detail: error instanceof Error ? error.message : String(error),
    })
    return redirectToDashboard(request, "oidc_exchange_failed")
  }
}

function redirectToDashboard(request: NextRequest, code: string): NextResponse {
  const response = NextResponse.redirect(
    new URL(`/dashboard?auth_error=${encodeURIComponent(code)}`, request.url),
    {
      status: 307,
      headers: { "Cache-Control": "no-store" },
    },
  )
  clearOidcTransientCookies(response)
  return response
}

function clearOidcTransientCookies(response: NextResponse): void {
  const clearOptions = getDashboardOidcClearCookieOptions()
  response.cookies.set(DASHBOARD_OIDC_STATE_COOKIE_NAME, "", clearOptions)
  response.cookies.set(DASHBOARD_OIDC_VERIFIER_COOKIE_NAME, "", clearOptions)
  response.cookies.set(DASHBOARD_OIDC_NONCE_COOKIE_NAME, "", clearOptions)
}
