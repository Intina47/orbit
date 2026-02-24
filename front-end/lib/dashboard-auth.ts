import { createHmac, timingSafeEqual } from "node:crypto"

import type { NextRequest } from "next/server"
import { NextResponse } from "next/server"

const DEFAULT_SESSION_TTL_SECONDS = 60 * 60 * 12
export const DASHBOARD_SESSION_COOKIE_NAME = "orbit_dashboard_session"
const NO_STORE_HEADERS = {
  "Cache-Control": "no-store",
}

type SessionPayload = {
  sub: string
  iat: number
  exp: number
}

export type DashboardAuthMode = "password" | "disabled"

export type DashboardSessionStatus = {
  authenticated: boolean
  mode: DashboardAuthMode
  subject?: string
}

export function getDashboardAuthMode(): DashboardAuthMode {
  const raw = process.env.ORBIT_DASHBOARD_AUTH_MODE?.trim().toLowerCase()
  return raw === "disabled" ? "disabled" : "password"
}

export function dashboardSessionConfigError(): string | null {
  if (getDashboardAuthMode() === "disabled") {
    return null
  }
  if (!readSessionSecret()) {
    return "Dashboard auth requires ORBIT_DASHBOARD_SESSION_SECRET to be set."
  }
  return null
}

export function dashboardLoginConfigError(): string | null {
  const sessionError = dashboardSessionConfigError()
  if (sessionError) {
    return sessionError
  }
  if (!readAuthPassword()) {
    return "Dashboard auth requires ORBIT_DASHBOARD_AUTH_PASSWORD to be set."
  }
  return null
}

export function buildDashboardSessionStatus(
  request: NextRequest,
): DashboardSessionStatus {
  const mode = getDashboardAuthMode()
  if (mode === "disabled") {
    return {
      authenticated: true,
      mode,
      subject: "dashboard-disabled",
    }
  }

  const rawCookie = request.cookies.get(DASHBOARD_SESSION_COOKIE_NAME)?.value ?? ""
  const payload = verifyDashboardSessionToken(rawCookie)
  if (!payload) {
    return {
      authenticated: false,
      mode,
    }
  }
  return {
    authenticated: true,
    mode,
    subject: payload.sub,
  }
}

export function requireDashboardSession(request: NextRequest): NextResponse | null {
  const configError = dashboardSessionConfigError()
  if (configError) {
    return NextResponse.json({ detail: configError }, { status: 500, headers: NO_STORE_HEADERS })
  }

  const mode = getDashboardAuthMode()
  if (mode === "disabled") {
    return null
  }

  const rawCookie = request.cookies.get(DASHBOARD_SESSION_COOKIE_NAME)?.value ?? ""
  const payload = verifyDashboardSessionToken(rawCookie)
  if (!payload) {
    return NextResponse.json(
      { detail: "Dashboard authentication required. Sign in first." },
      { status: 401, headers: NO_STORE_HEADERS },
    )
  }

  return null
}

export function verifyDashboardPassword(candidate: string): boolean {
  const configured = readAuthPassword()
  if (!configured) {
    return false
  }
  return safeCompare(configured, candidate)
}

export function createDashboardSessionToken(subject: string): string {
  const now = Math.floor(Date.now() / 1000)
  const payload: SessionPayload = {
    sub: subject,
    iat: now,
    exp: now + readSessionTtlSeconds(),
  }
  const encodedPayload = toBase64Url(JSON.stringify(payload))
  const signature = signPayload(encodedPayload)
  return `${encodedPayload}.${signature}`
}

export function getDashboardSessionCookieOptions(): {
  httpOnly: true
  secure: boolean
  sameSite: "strict"
  path: string
  maxAge: number
} {
  return {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "strict",
    path: "/",
    maxAge: readSessionTtlSeconds(),
  }
}

export function getDashboardSessionClearCookieOptions(): {
  httpOnly: true
  secure: boolean
  sameSite: "strict"
  path: string
  maxAge: number
} {
  return {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "strict",
    path: "/",
    maxAge: 0,
  }
}

function verifyDashboardSessionToken(token: string): SessionPayload | null {
  if (!token) {
    return null
  }
  const parts = token.split(".")
  if (parts.length !== 2) {
    return null
  }
  const [encodedPayload, providedSignature] = parts
  const expectedSignature = signPayload(encodedPayload)
  if (!safeCompare(expectedSignature, providedSignature)) {
    return null
  }

  const decodedPayload = fromBase64Url(encodedPayload)
  if (!decodedPayload) {
    return null
  }

  let payload: SessionPayload
  try {
    payload = JSON.parse(decodedPayload) as SessionPayload
  } catch {
    return null
  }

  if (!payload.sub || typeof payload.sub !== "string") {
    return null
  }
  if (!Number.isInteger(payload.exp) || payload.exp <= 0) {
    return null
  }
  const now = Math.floor(Date.now() / 1000)
  if (payload.exp <= now) {
    return null
  }
  return payload
}

function signPayload(value: string): string {
  const secret = readSessionSecret()
  if (!secret) {
    return ""
  }
  return createHmac("sha256", secret).update(value).digest("base64url")
}

function readSessionSecret(): string {
  return process.env.ORBIT_DASHBOARD_SESSION_SECRET?.trim() ?? ""
}

function readAuthPassword(): string {
  return process.env.ORBIT_DASHBOARD_AUTH_PASSWORD?.trim() ?? ""
}

function readSessionTtlSeconds(): number {
  const raw = process.env.ORBIT_DASHBOARD_SESSION_TTL_SECONDS?.trim()
  if (!raw) {
    return DEFAULT_SESSION_TTL_SECONDS
  }
  const parsed = Number.parseInt(raw, 10)
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return DEFAULT_SESSION_TTL_SECONDS
  }
  return parsed
}

function toBase64Url(value: string): string {
  return Buffer.from(value, "utf8").toString("base64url")
}

function fromBase64Url(value: string): string | null {
  try {
    return Buffer.from(value, "base64url").toString("utf8")
  } catch {
    return null
  }
}

function safeCompare(left: string, right: string): boolean {
  const leftBuffer = Buffer.from(left, "utf8")
  const rightBuffer = Buffer.from(right, "utf8")
  if (leftBuffer.length !== rightBuffer.length) {
    return false
  }
  return timingSafeEqual(leftBuffer, rightBuffer)
}
