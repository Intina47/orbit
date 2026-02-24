import { createHash, createHmac, randomBytes, timingSafeEqual } from "node:crypto"

import type { NextRequest } from "next/server"
import { NextResponse } from "next/server"

const DEFAULT_SESSION_TTL_SECONDS = 60 * 60 * 12
const DEFAULT_PROXY_TOKEN_TTL_SECONDS = 60 * 5
const DEFAULT_LOGIN_WINDOW_SECONDS = 60 * 15
const DEFAULT_LOGIN_MAX_ATTEMPTS = 10
const DEFAULT_LOGIN_LOCKOUT_SECONDS = 60 * 15
const OIDC_DISCOVERY_CACHE_TTL_MS = 10 * 60 * 1000

export const DASHBOARD_SESSION_COOKIE_NAME = "orbit_dashboard_session"
export const DASHBOARD_OIDC_STATE_COOKIE_NAME = "orbit_dashboard_oidc_state"
export const DASHBOARD_OIDC_VERIFIER_COOKIE_NAME = "orbit_dashboard_oidc_verifier"
export const DASHBOARD_OIDC_NONCE_COOKIE_NAME = "orbit_dashboard_oidc_nonce"

const NO_STORE_HEADERS = {
  "Cache-Control": "no-store",
}

type SessionProvider = "password" | "oidc" | "disabled"

type SessionPayload = {
  sub: string
  iss: string
  provider: SessionProvider
  iat: number
  exp: number
  email?: string
  name?: string
  tenant?: string
}

type OidcDiscoveryDocument = {
  issuer: string
  authorization_endpoint: string
  token_endpoint: string
  userinfo_endpoint?: string
}

type OidcTokenResponse = {
  access_token?: string
  id_token?: string
  token_type?: string
}

type LoginThrottleState = {
  windowStartMs: number
  failureCount: number
  lockUntilMs: number
}

type ProxyAuthMode = "exchange" | "static"
type JwtAlgorithm = "HS256" | "HS384" | "HS512"

export type DashboardAuthMode = "password" | "oidc" | "disabled"

export type DashboardPrincipal = {
  subject: string
  issuer: string
  provider: SessionProvider
  email?: string
  name?: string
  tenant?: string
}

export type DashboardSessionStatus = {
  authenticated: boolean
  mode: DashboardAuthMode
  subject?: string
  email?: string
  name?: string
  provider?: SessionProvider
  oidc_login_path?: string
}

export type ProxyTokenResult = {
  token: string
  accountKey: string
  principal: DashboardPrincipal
}

export type ProxyTokenResolution =
  | {
      ok: true
      token: string
      accountKey: string
      principal: DashboardPrincipal
    }
  | {
      ok: false
      status: number
      detail: string
    }

const loginThrottleStore = new Map<string, LoginThrottleState>()
let oidcDiscoveryCache:
  | {
      issuer: string
      fetchedAtMs: number
      document: OidcDiscoveryDocument
    }
  | null = null

export function getDashboardAuthMode(): DashboardAuthMode {
  const raw = process.env.ORBIT_DASHBOARD_AUTH_MODE?.trim().toLowerCase()
  if (raw === "disabled") {
    return "disabled"
  }
  if (raw === "oidc") {
    return "oidc"
  }
  return "password"
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

  const authMode = getDashboardAuthMode()
  if (authMode === "password") {
    if (!readAuthPassword()) {
      return "Dashboard auth requires ORBIT_DASHBOARD_AUTH_PASSWORD to be set."
    }
    return null
  }
  if (authMode === "oidc") {
    return dashboardOidcConfigError()
  }
  return null
}

export function dashboardOidcConfigError(): string | null {
  if (getDashboardAuthMode() !== "oidc") {
    return null
  }
  if (!readOidcIssuerUrl()) {
    return "OIDC mode requires ORBIT_DASHBOARD_OIDC_ISSUER_URL."
  }
  if (!readOidcClientId()) {
    return "OIDC mode requires ORBIT_DASHBOARD_OIDC_CLIENT_ID."
  }
  if (!readOidcClientSecret()) {
    return "OIDC mode requires ORBIT_DASHBOARD_OIDC_CLIENT_SECRET."
  }
  return null
}

export function dashboardProxyTokenConfigError(): string | null {
  const mode = resolveProxyAuthMode()
  if (mode === "static") {
    if (!readStaticProxyBearerToken()) {
      return "Dashboard proxy auth mode=static requires ORBIT_DASHBOARD_SERVER_BEARER_TOKEN."
    }
    return null
  }
  if (!readProxyJwtSecret()) {
    return "Dashboard proxy auth mode=exchange requires ORBIT_DASHBOARD_ORBIT_JWT_SECRET (or ORBIT_JWT_SECRET)."
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
      provider: "disabled",
    }
  }

  const principal = readPrincipalFromSession(request)
  if (!principal) {
    return {
      authenticated: false,
      mode,
      oidc_login_path: mode === "oidc" ? "/api/dashboard/auth/oidc/start" : undefined,
    }
  }
  return {
    authenticated: true,
    mode,
    subject: principal.subject,
    email: principal.email,
    name: principal.name,
    provider: principal.provider,
    oidc_login_path: mode === "oidc" ? "/api/dashboard/auth/oidc/start" : undefined,
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

  const principal = readPrincipalFromSession(request)
  if (!principal) {
    logDashboardAuthEvent("dashboard_session_missing", request)
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

export function getDashboardPrincipal(request: NextRequest): DashboardPrincipal | null {
  const mode = getDashboardAuthMode()
  if (mode === "disabled") {
    return {
      subject: "dashboard-disabled",
      issuer: "orbit-dashboard-disabled",
      provider: "disabled",
    }
  }
  return readPrincipalFromSession(request)
}

export function createDashboardSessionToken(principal: DashboardPrincipal): string {
  const now = Math.floor(Date.now() / 1000)
  const payload: SessionPayload = {
    sub: principal.subject,
    iss: principal.issuer,
    provider: principal.provider,
    email: principal.email,
    name: principal.name,
    tenant: principal.tenant,
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

export function getDashboardOidcTransientCookieOptions(): {
  httpOnly: true
  secure: boolean
  sameSite: "lax"
  path: string
  maxAge: number
} {
  return {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 10,
  }
}

export function getDashboardOidcClearCookieOptions(): {
  httpOnly: true
  secure: boolean
  sameSite: "lax"
  path: string
  maxAge: number
} {
  return {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: 0,
  }
}

export function enforceDashboardOrigin(request: NextRequest): NextResponse | null {
  const method = request.method.toUpperCase()
  if (method === "GET" || method === "HEAD" || method === "OPTIONS") {
    return null
  }

  const origin = request.headers.get("origin")?.trim() ?? ""
  if (!origin) {
    return null
  }
  const allowed = readAllowedOrigins(request)
  if (allowed.has(origin)) {
    return null
  }
  logDashboardAuthEvent("dashboard_origin_denied", request, { origin })
  return NextResponse.json(
    { detail: "Request origin is not allowed for dashboard mutation endpoints." },
    { status: 403, headers: NO_STORE_HEADERS },
  )
}

export function ensureDashboardLoginAllowed(request: NextRequest): NextResponse | null {
  const key = loginThrottleKey(request)
  const now = Date.now()
  const existing = loginThrottleStore.get(key)
  if (!existing) {
    return null
  }
  if (existing.lockUntilMs <= now) {
    loginThrottleStore.delete(key)
    return null
  }
  const retryAfterSeconds = Math.max(
    1,
    Math.ceil((existing.lockUntilMs - now) / 1000),
  )
  logDashboardAuthEvent("dashboard_login_locked", request, { retry_after: retryAfterSeconds })
  return NextResponse.json(
    { detail: "Too many failed sign-in attempts. Retry later." },
    {
      status: 429,
      headers: {
        ...NO_STORE_HEADERS,
        "Retry-After": String(retryAfterSeconds),
      },
    },
  )
}

export function recordDashboardLoginFailure(request: NextRequest): void {
  const key = loginThrottleKey(request)
  const now = Date.now()
  const maxAttempts = readLoginMaxAttempts()
  const windowMs = readLoginWindowSeconds() * 1000
  const lockoutMs = readLoginLockoutSeconds() * 1000

  const existing = loginThrottleStore.get(key)
  if (!existing || now - existing.windowStartMs > windowMs) {
    loginThrottleStore.set(key, {
      windowStartMs: now,
      failureCount: 1,
      lockUntilMs: 0,
    })
    return
  }

  existing.failureCount += 1
  if (existing.failureCount >= maxAttempts) {
    existing.lockUntilMs = now + lockoutMs
    existing.failureCount = 0
    existing.windowStartMs = now
  }
  loginThrottleStore.set(key, existing)
}

export function clearDashboardLoginFailures(request: NextRequest): void {
  loginThrottleStore.delete(loginThrottleKey(request))
}

export function logDashboardAuthEvent(
  event: string,
  request: NextRequest,
  metadata?: Record<string, unknown>,
): void {
  const payload: Record<string, unknown> = {
    ts: new Date().toISOString(),
    event,
    path: request.nextUrl.pathname,
    method: request.method.toUpperCase(),
    ip: extractClientIp(request),
  }
  const userAgent = request.headers.get("user-agent")?.trim()
  if (userAgent) {
    payload.ua = userAgent
  }
  if (metadata) {
    payload.meta = metadata
  }
  console.info(JSON.stringify(payload))
}

export async function buildOidcAuthorizationRequest(
  request: NextRequest,
): Promise<{
  authorizationUrl: string
  state: string
  nonce: string
  codeVerifier: string
}> {
  const configError = dashboardOidcConfigError()
  if (configError) {
    throw new Error(configError)
  }

  const discovery = await resolveOidcDiscovery()
  const state = randomToken()
  const nonce = randomToken()
  const codeVerifier = randomVerifier()
  const codeChallenge = toBase64Url(
    createHash("sha256").update(codeVerifier).digest(),
  )
  const redirectUri = resolveOidcRedirectUri(request)
  const scopes = readOidcScopes()

  const params = new URLSearchParams()
  params.set("client_id", readOidcClientId())
  params.set("redirect_uri", redirectUri)
  params.set("response_type", "code")
  params.set("scope", scopes.join(" "))
  params.set("state", state)
  params.set("nonce", nonce)
  params.set("code_challenge", codeChallenge)
  params.set("code_challenge_method", "S256")

  const prompt = process.env.ORBIT_DASHBOARD_OIDC_PROMPT?.trim()
  if (prompt) {
    params.set("prompt", prompt)
  }

  return {
    authorizationUrl: `${discovery.authorization_endpoint}?${params.toString()}`,
    state,
    nonce,
    codeVerifier,
  }
}

export async function exchangeOidcCodeForPrincipal(options: {
  request: NextRequest
  code: string
  codeVerifier: string
  expectedNonce?: string
}): Promise<DashboardPrincipal> {
  const configError = dashboardOidcConfigError()
  if (configError) {
    throw new Error(configError)
  }

  const discovery = await resolveOidcDiscovery()
  const redirectUri = resolveOidcRedirectUri(options.request)

  const tokenForm = new URLSearchParams()
  tokenForm.set("grant_type", "authorization_code")
  tokenForm.set("client_id", readOidcClientId())
  tokenForm.set("client_secret", readOidcClientSecret())
  tokenForm.set("code", options.code)
  tokenForm.set("redirect_uri", redirectUri)
  tokenForm.set("code_verifier", options.codeVerifier)

  const tokenResponse = await fetch(discovery.token_endpoint, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: tokenForm.toString(),
    cache: "no-store",
  })
  if (!tokenResponse.ok) {
    const body = await tokenResponse.text()
    throw new Error(
      `OIDC token exchange failed: ${tokenResponse.status} ${body.slice(0, 200)}`,
    )
  }

  let tokenPayload: OidcTokenResponse
  try {
    tokenPayload = (await tokenResponse.json()) as OidcTokenResponse
  } catch {
    throw new Error("OIDC token response was not valid JSON.")
  }

  const claims = await resolveOidcClaims({
    discovery,
    tokenPayload,
    expectedNonce: options.expectedNonce,
  })

  const subject = normalizeClaimValue(claims.sub)
  if (!subject) {
    throw new Error("OIDC claims missing subject.")
  }
  const issuer = normalizeClaimValue(claims.iss) || discovery.issuer
  const email = normalizeOptionalClaim(claims.email)
  const name = normalizeOptionalClaim(claims.name)
  const tenant = normalizeTenantClaim(claims)

  return {
    subject,
    issuer,
    provider: "oidc",
    ...(email ? { email } : {}),
    ...(name ? { name } : {}),
    ...(tenant ? { tenant } : {}),
  }
}

export function resolveProxyBearerToken(
  request: NextRequest,
  scopes: readonly string[],
): ProxyTokenResolution {
  const configError = dashboardProxyTokenConfigError()
  if (configError) {
    return { ok: false, status: 500, detail: configError }
  }

  const mode = resolveProxyAuthMode()
  if (mode === "static") {
    const token = readStaticProxyBearerToken()
    if (!token) {
      return {
        ok: false,
        status: 500,
        detail: "Missing ORBIT_DASHBOARD_SERVER_BEARER_TOKEN for static proxy auth mode.",
      }
    }
    return {
      ok: true,
      token,
      accountKey: "unknown",
      principal: {
        subject: "dashboard-static",
        issuer: "orbit-dashboard-static",
        provider: "disabled",
      },
    }
  }

  const principal = getDashboardPrincipal(request)
  if (!principal) {
    return {
      ok: false,
      status: 401,
      detail: "Dashboard authentication required. Sign in first.",
    }
  }

  const secret = readProxyJwtSecret()
  if (!secret) {
    return {
      ok: false,
      status: 500,
      detail: "Missing ORBIT_DASHBOARD_ORBIT_JWT_SECRET for token exchange.",
    }
  }

  const normalizedScopes = normalizeScopes(scopes)
  const accountKey = deriveAccountKey(principal)
  const token = signProxyJwt({
    principal,
    accountKey,
    secret,
    scopes: normalizedScopes,
  })
  return {
    ok: true,
    token,
    accountKey,
    principal,
  }
}

function readPrincipalFromSession(request: NextRequest): DashboardPrincipal | null {
  const rawCookie = request.cookies.get(DASHBOARD_SESSION_COOKIE_NAME)?.value ?? ""
  const payload = verifyDashboardSessionToken(rawCookie)
  if (!payload) {
    return null
  }
  return {
    subject: payload.sub,
    issuer: payload.iss,
    provider: payload.provider,
    ...(payload.email ? { email: payload.email } : {}),
    ...(payload.name ? { name: payload.name } : {}),
    ...(payload.tenant ? { tenant: payload.tenant } : {}),
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

  const subject = normalizeClaimValue(payload.sub)
  const issuer = normalizeClaimValue(payload.iss)
  const provider = normalizeProvider(payload.provider)
  if (!subject || !issuer || !provider) {
    return null
  }
  if (!Number.isInteger(payload.exp) || payload.exp <= 0) {
    return null
  }
  const now = Math.floor(Date.now() / 1000)
  if (payload.exp <= now) {
    return null
  }
  return {
    sub: subject,
    iss: issuer,
    provider,
    iat: payload.iat,
    exp: payload.exp,
    ...(payload.email ? { email: payload.email } : {}),
    ...(payload.name ? { name: payload.name } : {}),
    ...(payload.tenant ? { tenant: payload.tenant } : {}),
  }
}

function signPayload(value: string): string {
  const secret = readSessionSecret()
  if (!secret) {
    return ""
  }
  return createHmac("sha256", secret).update(value).digest("base64url")
}

function signProxyJwt(options: {
  principal: DashboardPrincipal
  accountKey: string
  secret: string
  scopes: string[]
}): string {
  const algorithm = readProxyJwtAlgorithm()
  const now = Math.floor(Date.now() / 1000)
  const payload: Record<string, unknown> = {
    sub: options.principal.subject,
    iat: now,
    exp: now + readProxyJwtTtlSeconds(),
    iss: readProxyJwtIssuer(),
    aud: readProxyJwtAudience(),
    scopes: options.scopes,
    scope: options.scopes.join(" "),
    account_key: options.accountKey,
    auth_subject: options.principal.subject,
    auth_issuer: options.principal.issuer,
    auth_type: "dashboard_proxy",
    ...(options.principal.email ? { email: options.principal.email } : {}),
    ...(options.principal.tenant ? { tenant: options.principal.tenant } : {}),
    jti: randomToken(),
  }
  const header = {
    alg: algorithm,
    typ: "JWT",
  }
  const encodedHeader = toBase64Url(JSON.stringify(header))
  const encodedPayload = toBase64Url(JSON.stringify(payload))
  const signingInput = `${encodedHeader}.${encodedPayload}`
  const digestName = algorithm === "HS512" ? "sha512" : algorithm === "HS384" ? "sha384" : "sha256"
  const signature = createHmac(digestName, options.secret)
    .update(signingInput)
    .digest("base64url")
  return `${signingInput}.${signature}`
}

function deriveAccountKey(principal: DashboardPrincipal): string {
  const seed = principal.tenant
    ? `tenant:${principal.issuer}:${principal.tenant}`
    : `subject:${principal.issuer}:${principal.subject}`
  const digest = createHash("sha256").update(seed).digest("hex")
  return `acct_${digest.slice(0, 24)}`
}

async function resolveOidcDiscovery(): Promise<OidcDiscoveryDocument> {
  const issuerUrl = readOidcIssuerUrl()
  const now = Date.now()
  if (
    oidcDiscoveryCache !== null
    && oidcDiscoveryCache.issuer === issuerUrl
    && now - oidcDiscoveryCache.fetchedAtMs < OIDC_DISCOVERY_CACHE_TTL_MS
  ) {
    return oidcDiscoveryCache.document
  }

  const discoveryUrl = issuerUrl.endsWith("/.well-known/openid-configuration")
    ? issuerUrl
    : `${issuerUrl.replace(/\/+$/, "")}/.well-known/openid-configuration`
  const response = await fetch(discoveryUrl, {
    method: "GET",
    headers: {
      Accept: "application/json",
    },
    cache: "no-store",
  })
  if (!response.ok) {
    const body = await response.text()
    throw new Error(
      `OIDC discovery failed: ${response.status} ${body.slice(0, 200)}`,
    )
  }

  let payload: Record<string, unknown>
  try {
    payload = (await response.json()) as Record<string, unknown>
  } catch {
    throw new Error("OIDC discovery response was not valid JSON.")
  }
  const document: OidcDiscoveryDocument = {
    issuer: normalizeClaimValue(payload.issuer) || issuerUrl,
    authorization_endpoint: requireUrl(payload.authorization_endpoint, "authorization_endpoint"),
    token_endpoint: requireUrl(payload.token_endpoint, "token_endpoint"),
    ...(typeof payload.userinfo_endpoint === "string"
      ? { userinfo_endpoint: payload.userinfo_endpoint }
      : {}),
  }
  oidcDiscoveryCache = {
    issuer: issuerUrl,
    fetchedAtMs: now,
    document,
  }
  return document
}

async function resolveOidcClaims(options: {
  discovery: OidcDiscoveryDocument
  tokenPayload: OidcTokenResponse
  expectedNonce?: string
}): Promise<Record<string, unknown>> {
  const accessToken = options.tokenPayload.access_token?.trim()
  const idToken = options.tokenPayload.id_token?.trim()
  let idTokenClaims: Record<string, unknown> | null = null
  if (idToken) {
    idTokenClaims = decodeJwtPayload(idToken)
    if (!idTokenClaims) {
      throw new Error("Failed to decode OIDC id_token payload.")
    }
    const expectedNonce = options.expectedNonce?.trim()
    if (expectedNonce) {
      const actualNonce = normalizeClaimValue(idTokenClaims.nonce)
      if (!actualNonce || actualNonce !== expectedNonce) {
        throw new Error("OIDC nonce validation failed.")
      }
    }
  }

  if (options.discovery.userinfo_endpoint && accessToken) {
    const userInfoResponse = await fetch(options.discovery.userinfo_endpoint, {
      method: "GET",
      headers: {
        Accept: "application/json",
        Authorization: `Bearer ${accessToken}`,
      },
      cache: "no-store",
    })
    if (userInfoResponse.ok) {
      try {
        const userInfoClaims = (await userInfoResponse.json()) as Record<string, unknown>
        return {
          ...(idTokenClaims ?? {}),
          ...userInfoClaims,
        }
      } catch {
        // fall through to id_token decode
      }
    }
  }

  if (!idTokenClaims) {
    throw new Error("OIDC token response missing both usable userinfo and id_token.")
  }
  return idTokenClaims
}

function decodeJwtPayload(token: string): Record<string, unknown> | null {
  const parts = token.split(".")
  if (parts.length < 2) {
    return null
  }
  const decodedPayload = fromBase64Url(parts[1])
  if (!decodedPayload) {
    return null
  }
  try {
    return JSON.parse(decodedPayload) as Record<string, unknown>
  } catch {
    return null
  }
}

function requireUrl(value: unknown, label: string): string {
  const normalized = normalizeClaimValue(value)
  if (!normalized) {
    throw new Error(`OIDC discovery missing ${label}.`)
  }
  return normalized
}

function normalizeProvider(value: unknown): SessionProvider | null {
  const normalized = normalizeClaimValue(value)
  if (!normalized) {
    return null
  }
  if (normalized === "password" || normalized === "oidc" || normalized === "disabled") {
    return normalized
  }
  return null
}

function normalizeClaimValue(value: unknown): string {
  if (typeof value !== "string") {
    return ""
  }
  const normalized = value.trim()
  if (!normalized) {
    return ""
  }
  if (normalized.length > 255) {
    return normalized.slice(0, 255)
  }
  return normalized
}

function normalizeOptionalClaim(value: unknown): string | undefined {
  const normalized = normalizeClaimValue(value)
  return normalized || undefined
}

function normalizeTenantClaim(claims: Record<string, unknown>): string | undefined {
  const customKeys = (process.env.ORBIT_DASHBOARD_OIDC_TENANT_CLAIMS?.trim() ?? "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean)
  const candidates: unknown[] = customKeys.map((key) => claims[key])
  candidates.push(
    claims.tid,
    claims.tenant,
    claims.org,
    claims.organization,
    claims.org_id,
    claims.hd,
  )
  for (const candidate of candidates) {
    const normalized = normalizeClaimValue(candidate)
    if (normalized) {
      return normalized
    }
  }
  return undefined
}

function resolveOidcRedirectUri(request: NextRequest): string {
  const configured = process.env.ORBIT_DASHBOARD_OIDC_REDIRECT_URI?.trim()
  if (configured) {
    return configured
  }
  return `${request.nextUrl.origin}/api/dashboard/auth/oidc/callback`
}

function readOidcIssuerUrl(): string {
  return process.env.ORBIT_DASHBOARD_OIDC_ISSUER_URL?.trim() ?? ""
}

function readOidcClientId(): string {
  return process.env.ORBIT_DASHBOARD_OIDC_CLIENT_ID?.trim() ?? ""
}

function readOidcClientSecret(): string {
  return process.env.ORBIT_DASHBOARD_OIDC_CLIENT_SECRET?.trim() ?? ""
}

function readOidcScopes(): string[] {
  const raw = process.env.ORBIT_DASHBOARD_OIDC_SCOPES?.trim()
  if (!raw) {
    return ["openid", "profile", "email"]
  }
  return normalizeScopes(raw.split(/\s+/))
}

function resolveProxyAuthMode(): ProxyAuthMode {
  const configured = process.env.ORBIT_DASHBOARD_PROXY_AUTH_MODE?.trim().toLowerCase()
  if (configured === "static") {
    return "static"
  }
  if (configured === "exchange") {
    return "exchange"
  }
  if (readProxyJwtSecret()) {
    return "exchange"
  }
  if (readStaticProxyBearerToken()) {
    return "static"
  }
  return "exchange"
}

function readProxyJwtSecret(): string {
  return (
    process.env.ORBIT_DASHBOARD_ORBIT_JWT_SECRET?.trim()
    || process.env.ORBIT_JWT_SECRET?.trim()
    || ""
  )
}

function readProxyJwtIssuer(): string {
  return (
    process.env.ORBIT_DASHBOARD_ORBIT_JWT_ISSUER?.trim()
    || process.env.ORBIT_JWT_ISSUER?.trim()
    || "orbit"
  )
}

function readProxyJwtAudience(): string {
  return (
    process.env.ORBIT_DASHBOARD_ORBIT_JWT_AUDIENCE?.trim()
    || process.env.ORBIT_JWT_AUDIENCE?.trim()
    || "orbit-api"
  )
}

function readProxyJwtAlgorithm(): JwtAlgorithm {
  const raw = process.env.ORBIT_DASHBOARD_ORBIT_JWT_ALGORITHM?.trim().toUpperCase()
  if (raw === "HS512" || raw === "HS384" || raw === "HS256") {
    return raw
  }
  return "HS256"
}

function readProxyJwtTtlSeconds(): number {
  const raw = process.env.ORBIT_DASHBOARD_ORBIT_JWT_TTL_SECONDS?.trim()
  if (!raw) {
    return DEFAULT_PROXY_TOKEN_TTL_SECONDS
  }
  const parsed = Number.parseInt(raw, 10)
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return DEFAULT_PROXY_TOKEN_TTL_SECONDS
  }
  return parsed
}

function readStaticProxyBearerToken(): string {
  return process.env.ORBIT_DASHBOARD_SERVER_BEARER_TOKEN?.trim() ?? ""
}

function readAllowedOrigins(request: NextRequest): Set<string> {
  const configured = process.env.ORBIT_DASHBOARD_ALLOWED_ORIGINS?.trim()
  const values = configured
    ? configured
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean)
    : []
  if (values.length === 0) {
    values.push(request.nextUrl.origin)
  }
  return new Set(values)
}

function loginThrottleKey(request: NextRequest): string {
  const ip = extractClientIp(request) || "unknown"
  const userAgent = request.headers.get("user-agent")?.trim().slice(0, 80) ?? "unknown"
  return `${ip}|${userAgent}`
}

function extractClientIp(request: NextRequest): string {
  const forwarded = request.headers.get("x-forwarded-for")?.trim()
  if (forwarded) {
    return forwarded.split(",")[0]?.trim() || "unknown"
  }
  const realIp = request.headers.get("x-real-ip")?.trim()
  if (realIp) {
    return realIp
  }
  return "unknown"
}

function readLoginWindowSeconds(): number {
  const raw = process.env.ORBIT_DASHBOARD_LOGIN_WINDOW_SECONDS?.trim()
  if (!raw) {
    return DEFAULT_LOGIN_WINDOW_SECONDS
  }
  const parsed = Number.parseInt(raw, 10)
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return DEFAULT_LOGIN_WINDOW_SECONDS
  }
  return parsed
}

function readLoginMaxAttempts(): number {
  const raw = process.env.ORBIT_DASHBOARD_LOGIN_MAX_ATTEMPTS?.trim()
  if (!raw) {
    return DEFAULT_LOGIN_MAX_ATTEMPTS
  }
  const parsed = Number.parseInt(raw, 10)
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return DEFAULT_LOGIN_MAX_ATTEMPTS
  }
  return parsed
}

function readLoginLockoutSeconds(): number {
  const raw = process.env.ORBIT_DASHBOARD_LOGIN_LOCKOUT_SECONDS?.trim()
  if (!raw) {
    return DEFAULT_LOGIN_LOCKOUT_SECONDS
  }
  const parsed = Number.parseInt(raw, 10)
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return DEFAULT_LOGIN_LOCKOUT_SECONDS
  }
  return parsed
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

function randomToken(): string {
  return randomBytes(24).toString("base64url")
}

function randomVerifier(): string {
  return randomBytes(48).toString("base64url")
}

function normalizeScopes(input: readonly string[]): string[] {
  const seen = new Set<string>()
  const normalized: string[] = []
  for (const item of input) {
    const value = item.trim()
    if (!value || seen.has(value)) {
      continue
    }
    seen.add(value)
    normalized.push(value)
  }
  return normalized
}

function toBase64Url(value: string | Buffer): string {
  return Buffer.from(value).toString("base64url")
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
