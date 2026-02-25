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
export const DASHBOARD_OIDC_PROVIDER_COOKIE_NAME = "orbit_dashboard_oidc_provider"

const NO_STORE_HEADERS = {
  "Cache-Control": "no-store",
}

type SessionProvider = "password" | "oidc" | "disabled"

type OidcProviderProtocol = "oidc" | "oauth2"
type OidcProviderId = "google" | "github" | "sso"

type OidcProviderConfig = {
  id: OidcProviderId
  label: string
  protocol: OidcProviderProtocol
  issuer: string
  clientId: string
  clientSecret: string
  scopes: string[]
  redirectUri?: string
  prompt?: string
  tenantClaimKeys: string[]
  authorizationEndpoint?: string
  tokenEndpoint?: string
  userinfoEndpoint?: string
  emailEndpoint?: string
}

type SessionPayload = {
  sub: string
  iss: string
  provider: SessionProvider
  iat: number
  exp: number
  email?: string
  name?: string
  tenant?: string
  auth_provider?: string
  picture?: string
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
  authProvider?: string
  picture?: string
}

export type DashboardOidcLoginProvider = {
  id: string
  label: string
  path: string
}

export type DashboardSessionStatus = {
  authenticated: boolean
  mode: DashboardAuthMode
  subject?: string
  email?: string
  name?: string
  provider?: SessionProvider
  auth_provider?: string
  picture?: string
  oidc_login_path?: string
  oidc_login_providers?: DashboardOidcLoginProvider[]
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
const oidcDiscoveryCache = new Map<
  string,
  {
    fetchedAtMs: number
    document: OidcDiscoveryDocument
  }
>()

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
  const providers = resolveConfiguredOidcProviders()
  if (providers.length === 0) {
    return (
      "OIDC mode requires provider config. Set Google with "
      + "ORBIT_DASHBOARD_OIDC_GOOGLE_CLIENT_ID/SECRET, GitHub with "
      + "ORBIT_DASHBOARD_OIDC_GITHUB_CLIENT_ID/SECRET, or legacy "
      + "ORBIT_DASHBOARD_OIDC_ISSUER_URL/CLIENT_ID/CLIENT_SECRET."
    )
  }
  for (const provider of providers) {
    if (!provider.clientId) {
      return `OIDC provider "${provider.id}" requires a client ID.`
    }
    if (!provider.clientSecret) {
      return `OIDC provider "${provider.id}" requires a client secret.`
    }
    if (provider.protocol === "oidc" && !provider.issuer) {
      return `OIDC provider "${provider.id}" requires an issuer URL.`
    }
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
  const oidcProviders = mode === "oidc" ? buildOidcLoginProviders(request) : []
  const primaryOidcPath = oidcProviders[0]?.path
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
      oidc_login_path: primaryOidcPath,
      oidc_login_providers: oidcProviders,
    }
  }
  return {
    authenticated: true,
    mode,
    subject: principal.subject,
    email: principal.email,
    name: principal.name,
    provider: principal.provider,
    auth_provider: principal.authProvider,
    picture: principal.picture,
    oidc_login_path: primaryOidcPath,
    oidc_login_providers: oidcProviders,
  }
}

function buildOidcLoginProviders(request: NextRequest): DashboardOidcLoginProvider[] {
  const configured = resolveConfiguredOidcProviders(request)
  return configured.map((provider) => ({
    id: provider.id,
    label: provider.label,
    path: `/api/dashboard/auth/oidc/start?provider=${encodeURIComponent(provider.id)}`,
  }))
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
    auth_provider: principal.authProvider,
    picture: principal.picture,
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

  const originHeader = request.headers.get("origin")?.trim() ?? ""
  const refererHeader = request.headers.get("referer")?.trim() ?? ""
  const origin = extractRequestOrigin(originHeader, refererHeader)
  if (!origin) {
    if (readAllowMissingOriginForMutations()) {
      return null
    }
    logDashboardAuthEvent("dashboard_origin_missing", request, {
      origin_header: originHeader || undefined,
      referer_header: refererHeader || undefined,
    })
    return NextResponse.json(
      { detail: "Origin or Referer header is required for dashboard mutation endpoints." },
      { status: 403, headers: NO_STORE_HEADERS },
    )
  }
  const allowed = readAllowedOrigins(request)
  if (allowed.has(origin)) {
    return null
  }
  logDashboardAuthEvent("dashboard_origin_denied", request, {
    origin,
    origin_header: originHeader || undefined,
    referer_header: refererHeader || undefined,
  })
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
  providerHint?: string,
): Promise<{
  authorizationUrl: string
  state: string
  nonce: string
  codeVerifier: string
  providerId: string
}> {
  const configError = dashboardOidcConfigError()
  if (configError) {
    throw new Error(configError)
  }

  const provider = resolveOidcProviderConfig({
    request,
    providerHint,
  })
  const authorizationEndpoint = provider.protocol === "oidc"
    ? (await resolveOidcDiscovery(provider)).authorization_endpoint
    : requireProviderEndpoint(provider.authorizationEndpoint, "authorization endpoint")
  const state = randomToken()
  const nonce = randomToken()
  const codeVerifier = randomVerifier()
  const codeChallenge = toBase64Url(
    createHash("sha256").update(codeVerifier).digest(),
  )
  const redirectUri = resolveOidcRedirectUri(request, provider)
  const scopes = provider.scopes

  const params = new URLSearchParams()
  params.set("client_id", provider.clientId)
  params.set("redirect_uri", redirectUri)
  params.set("response_type", "code")
  params.set("scope", scopes.join(" "))
  params.set("state", state)
  params.set("code_challenge", codeChallenge)
  params.set("code_challenge_method", "S256")
  if (provider.protocol === "oidc") {
    params.set("nonce", nonce)
  }

  const prompt = provider.prompt
  if (prompt) {
    params.set("prompt", prompt)
  }
  if (provider.id === "github") {
    params.set("allow_signup", "true")
  }

  return {
    authorizationUrl: `${authorizationEndpoint}?${params.toString()}`,
    state,
    nonce,
    codeVerifier,
    providerId: provider.id,
  }
}

export async function exchangeOidcCodeForPrincipal(options: {
  request: NextRequest
  code: string
  codeVerifier: string
  expectedNonce?: string
  providerId: string
}): Promise<DashboardPrincipal> {
  const configError = dashboardOidcConfigError()
  if (configError) {
    throw new Error(configError)
  }

  const provider = resolveOidcProviderConfig({
    request: options.request,
    providerHint: options.providerId,
  })
  if (provider.protocol === "oauth2" && provider.id === "github") {
    return exchangeGithubCodeForPrincipal({
      provider,
      code: options.code,
      codeVerifier: options.codeVerifier,
      request: options.request,
    })
  }
  const discovery = await resolveOidcDiscovery(provider)
  const redirectUri = resolveOidcRedirectUri(options.request, provider)

  const tokenForm = new URLSearchParams()
  tokenForm.set("grant_type", "authorization_code")
  tokenForm.set("client_id", provider.clientId)
  tokenForm.set("client_secret", provider.clientSecret)
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
    provider,
  })

  const subject = normalizeClaimValue(claims.sub)
  if (!subject) {
    throw new Error("OIDC claims missing subject.")
  }
  const issuer = normalizeClaimValue(claims.iss) || discovery.issuer || provider.issuer
  const email = normalizeOptionalClaim(claims.email)
  const name = normalizeOptionalClaim(claims.name)
  const tenant = normalizeTenantClaim(claims, provider)
  const picture = normalizeOptionalUrlClaim(claims.picture)

  return {
    subject,
    issuer,
    provider: "oidc",
    authProvider: provider.id,
    ...(email ? { email } : {}),
    ...(name ? { name } : {}),
    ...(tenant ? { tenant } : {}),
    ...(picture ? { picture } : {}),
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
    ...(payload.auth_provider ? { authProvider: payload.auth_provider } : {}),
    ...(payload.picture ? { picture: payload.picture } : {}),
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
    ...(payload.auth_provider ? { auth_provider: payload.auth_provider } : {}),
    ...(payload.picture ? { picture: payload.picture } : {}),
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
    ...(options.principal.name ? { name: options.principal.name } : {}),
    ...(options.principal.picture ? { picture: options.principal.picture } : {}),
    ...(options.principal.authProvider ? { auth_provider: options.principal.authProvider } : {}),
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

async function resolveOidcDiscovery(
  provider: OidcProviderConfig,
): Promise<OidcDiscoveryDocument> {
  const issuerUrl = provider.issuer.trim()
  if (!issuerUrl) {
    throw new Error(`OIDC provider "${provider.id}" is missing issuer URL.`)
  }
  const now = Date.now()
  const cached = oidcDiscoveryCache.get(issuerUrl)
  if (cached && now - cached.fetchedAtMs < OIDC_DISCOVERY_CACHE_TTL_MS) {
    return cached.document
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
      `OIDC discovery failed (${provider.id}): ${response.status} ${body.slice(0, 200)}`,
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
  oidcDiscoveryCache.set(issuerUrl, {
    fetchedAtMs: now,
    document,
  })
  return document
}

async function resolveOidcClaims(options: {
  discovery: OidcDiscoveryDocument
  tokenPayload: OidcTokenResponse
  expectedNonce?: string
  provider: OidcProviderConfig
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
    validateIdTokenBasicClaims(idTokenClaims, options)
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
        const idTokenSubject = normalizeClaimValue(idTokenClaims?.sub)
        const userInfoSubject = normalizeClaimValue(userInfoClaims.sub)
        if (idTokenSubject && userInfoSubject && idTokenSubject !== userInfoSubject) {
          throw new Error("OIDC subject mismatch between id_token and userinfo response.")
        }
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
    throw new Error(
      `OIDC token response missing both usable userinfo and id_token for provider ${options.provider.id}.`,
    )
  }
  if (!readAllowUnsignedIdTokenFallback()) {
    throw new Error(
      "OIDC userinfo endpoint is unavailable. For security, unsigned id_token fallback is disabled "
      + "by default. Configure a provider with userinfo support or set "
      + "ORBIT_DASHBOARD_OIDC_ALLOW_UNSIGNED_ID_TOKEN_FALLBACK=true if you accept this risk.",
    )
  }
  return idTokenClaims
}

function validateIdTokenBasicClaims(
  idTokenClaims: Record<string, unknown>,
  options: {
    discovery: OidcDiscoveryDocument
    provider: OidcProviderConfig
  },
): void {
  const issuerClaim = normalizeClaimValue(idTokenClaims.iss)
  if (issuerClaim && issuerClaim !== options.discovery.issuer) {
    throw new Error("OIDC id_token issuer claim did not match discovered issuer.")
  }
  const audClaim = idTokenClaims.aud
  if (typeof audClaim === "string") {
    const normalizedAud = normalizeClaimValue(audClaim)
    if (normalizedAud && normalizedAud !== options.provider.clientId) {
      throw new Error("OIDC id_token audience claim did not match client_id.")
    }
    return
  }
  if (!Array.isArray(audClaim)) {
    return
  }
  const audiences = audClaim
    .map((value) => normalizeClaimValue(value))
    .filter(Boolean)
  if (audiences.length > 0 && !audiences.includes(options.provider.clientId)) {
    throw new Error("OIDC id_token audience claim did not include client_id.")
  }
}

async function exchangeGithubCodeForPrincipal(options: {
  provider: OidcProviderConfig
  request: NextRequest
  code: string
  codeVerifier: string
}): Promise<DashboardPrincipal> {
  const redirectUri = resolveOidcRedirectUri(options.request, options.provider)
  const tokenEndpoint = requireProviderEndpoint(
    options.provider.tokenEndpoint,
    "token endpoint",
  )

  const tokenForm = new URLSearchParams()
  tokenForm.set("client_id", options.provider.clientId)
  tokenForm.set("client_secret", options.provider.clientSecret)
  tokenForm.set("code", options.code)
  tokenForm.set("redirect_uri", redirectUri)
  tokenForm.set("code_verifier", options.codeVerifier)

  const tokenResponse = await fetch(tokenEndpoint, {
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
      `GitHub token exchange failed: ${tokenResponse.status} ${body.slice(0, 200)}`,
    )
  }

  let tokenPayload: OidcTokenResponse
  try {
    tokenPayload = (await tokenResponse.json()) as OidcTokenResponse
  } catch {
    throw new Error("GitHub token response was not valid JSON.")
  }
  const accessToken = tokenPayload.access_token?.trim()
  if (!accessToken) {
    throw new Error("GitHub token response missing access_token.")
  }

  const claims = await resolveGithubUserClaims(options.provider, accessToken)
  const subject = normalizeGithubSubject(claims)
  if (!subject) {
    throw new Error("GitHub userinfo payload missing id/login.")
  }

  const emailFromUser = normalizeOptionalClaim(claims.email)
  const email = emailFromUser ?? (await resolveGithubPrimaryEmail(options.provider, accessToken))
  const name = normalizeOptionalClaim(claims.name) || normalizeOptionalClaim(claims.login)
  const picture = normalizeOptionalUrlClaim(claims.avatar_url)

  return {
    subject,
    issuer: options.provider.issuer,
    provider: "oidc",
    authProvider: options.provider.id,
    ...(email ? { email } : {}),
    ...(name ? { name } : {}),
    ...(picture ? { picture } : {}),
  }
}

async function resolveGithubUserClaims(
  provider: OidcProviderConfig,
  accessToken: string,
): Promise<Record<string, unknown>> {
  const userinfoEndpoint = requireProviderEndpoint(
    provider.userinfoEndpoint,
    "userinfo endpoint",
  )
  const response = await fetch(userinfoEndpoint, {
    method: "GET",
    headers: {
      Accept: "application/json",
      Authorization: `Bearer ${accessToken}`,
      "X-GitHub-Api-Version": "2022-11-28",
    },
    cache: "no-store",
  })
  if (!response.ok) {
    const body = await response.text()
    throw new Error(
      `GitHub userinfo request failed: ${response.status} ${body.slice(0, 200)}`,
    )
  }
  try {
    return (await response.json()) as Record<string, unknown>
  } catch {
    throw new Error("GitHub userinfo payload was not valid JSON.")
  }
}

async function resolveGithubPrimaryEmail(
  provider: OidcProviderConfig,
  accessToken: string,
): Promise<string | undefined> {
  const emailEndpoint = provider.emailEndpoint?.trim()
  if (!emailEndpoint) {
    return undefined
  }
  const response = await fetch(emailEndpoint, {
    method: "GET",
    headers: {
      Accept: "application/json",
      Authorization: `Bearer ${accessToken}`,
      "X-GitHub-Api-Version": "2022-11-28",
    },
    cache: "no-store",
  })
  if (!response.ok) {
    return undefined
  }
  let payload: unknown
  try {
    payload = await response.json()
  } catch {
    return undefined
  }
  if (!Array.isArray(payload)) {
    return undefined
  }
  const candidates = payload
    .map((item) => (typeof item === "object" && item !== null ? item : {}))
    .map((item) => ({
      email: normalizeOptionalClaim((item as Record<string, unknown>).email),
      primary: Boolean((item as Record<string, unknown>).primary),
      verified: Boolean((item as Record<string, unknown>).verified),
    }))
    .filter((item) => Boolean(item.email))
  const primaryVerified = candidates.find((item) => item.primary && item.verified)
  if (primaryVerified?.email) {
    return primaryVerified.email
  }
  const verified = candidates.find((item) => item.verified)
  if (verified?.email) {
    return verified.email
  }
  return candidates[0]?.email
}

function normalizeGithubSubject(claims: Record<string, unknown>): string {
  const numericId = claims.id
  if (typeof numericId === "number" && Number.isFinite(numericId)) {
    return `github:${Math.trunc(numericId)}`
  }
  if (typeof numericId === "string" && numericId.trim()) {
    return `github:${numericId.trim()}`
  }
  const login = normalizeClaimValue(claims.login)
  if (!login) {
    return ""
  }
  return `github_login:${login}`
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

function normalizeOptionalUrlClaim(value: unknown): string | undefined {
  const normalized = normalizeClaimValue(value)
  if (!normalized) {
    return undefined
  }
  if (!normalized.startsWith("http://") && !normalized.startsWith("https://")) {
    return undefined
  }
  if (normalized.length > 1024) {
    return normalized.slice(0, 1024)
  }
  return normalized
}

function normalizeTenantClaim(
  claims: Record<string, unknown>,
  provider: OidcProviderConfig,
): string | undefined {
  const customKeys = provider.tenantClaimKeys
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

function resolveOidcRedirectUri(
  request: NextRequest,
  provider: OidcProviderConfig,
): string {
  const configured = provider.redirectUri?.trim() || process.env.ORBIT_DASHBOARD_OIDC_REDIRECT_URI?.trim()
  if (configured) {
    return configured
  }
  return `${request.nextUrl.origin}/api/dashboard/auth/oidc/callback`
}

function resolveOidcProviderConfig(options: {
  request: NextRequest
  providerHint?: string
}): OidcProviderConfig {
  const configured = resolveConfiguredOidcProviders(options.request)
  if (configured.length === 0) {
    throw new Error(
      "OIDC mode is enabled but no providers are configured.",
    )
  }
  const normalizedHint = options.providerHint?.trim().toLowerCase()
  if (!normalizedHint) {
    return configured[0]
  }
  const selected = configured.find((provider) => provider.id === normalizedHint)
  if (!selected) {
    throw new Error(`Unsupported OIDC provider "${normalizedHint}".`)
  }
  return selected
}

function resolveConfiguredOidcProviders(
  request?: NextRequest,
): OidcProviderConfig[] {
  const providers: OidcProviderConfig[] = []
  const google = readGoogleProviderConfig(request)
  if (google !== null) {
    providers.push(google)
  }
  const github = readGithubProviderConfig(request)
  if (github !== null) {
    providers.push(github)
  }
  if (providers.length > 0) {
    return providers
  }
  const legacy = readLegacyOidcProviderConfig(request)
  if (legacy !== null) {
    providers.push(legacy)
  }
  return providers
}

function readGoogleProviderConfig(
  request?: NextRequest,
): OidcProviderConfig | null {
  const clientId = process.env.ORBIT_DASHBOARD_OIDC_GOOGLE_CLIENT_ID?.trim() ?? ""
  const clientSecret = process.env.ORBIT_DASHBOARD_OIDC_GOOGLE_CLIENT_SECRET?.trim() ?? ""
  if (!clientId && !clientSecret) {
    return null
  }
  const issuer = process.env.ORBIT_DASHBOARD_OIDC_GOOGLE_ISSUER_URL?.trim() || "https://accounts.google.com"
  return {
    id: "google",
    label: "Continue with Google",
    protocol: "oidc",
    issuer,
    clientId,
    clientSecret,
    scopes: readScopeEnv("ORBIT_DASHBOARD_OIDC_GOOGLE_SCOPES", ["openid", "profile", "email"]),
    redirectUri: process.env.ORBIT_DASHBOARD_OIDC_GOOGLE_REDIRECT_URI?.trim() || resolveSharedRedirectUri(request),
    prompt: process.env.ORBIT_DASHBOARD_OIDC_GOOGLE_PROMPT?.trim() || "select_account",
    tenantClaimKeys: readTenantClaimKeys("ORBIT_DASHBOARD_OIDC_GOOGLE_TENANT_CLAIMS"),
  }
}

function readGithubProviderConfig(
  request?: NextRequest,
): OidcProviderConfig | null {
  const clientId = process.env.ORBIT_DASHBOARD_OIDC_GITHUB_CLIENT_ID?.trim() ?? ""
  const clientSecret = process.env.ORBIT_DASHBOARD_OIDC_GITHUB_CLIENT_SECRET?.trim() ?? ""
  if (!clientId && !clientSecret) {
    return null
  }
  return {
    id: "github",
    label: "Continue with GitHub",
    protocol: "oauth2",
    issuer: process.env.ORBIT_DASHBOARD_OIDC_GITHUB_ISSUER_URL?.trim() || "https://github.com",
    clientId,
    clientSecret,
    scopes: readScopeEnv("ORBIT_DASHBOARD_OIDC_GITHUB_SCOPES", ["read:user", "user:email"]),
    redirectUri: process.env.ORBIT_DASHBOARD_OIDC_GITHUB_REDIRECT_URI?.trim() || resolveSharedRedirectUri(request),
    prompt: undefined,
    tenantClaimKeys: readTenantClaimKeys("ORBIT_DASHBOARD_OIDC_GITHUB_TENANT_CLAIMS"),
    authorizationEndpoint: process.env.ORBIT_DASHBOARD_OIDC_GITHUB_AUTHORIZATION_ENDPOINT?.trim()
      || "https://github.com/login/oauth/authorize",
    tokenEndpoint: process.env.ORBIT_DASHBOARD_OIDC_GITHUB_TOKEN_ENDPOINT?.trim()
      || "https://github.com/login/oauth/access_token",
    userinfoEndpoint: process.env.ORBIT_DASHBOARD_OIDC_GITHUB_USERINFO_ENDPOINT?.trim()
      || "https://api.github.com/user",
    emailEndpoint: process.env.ORBIT_DASHBOARD_OIDC_GITHUB_EMAILS_ENDPOINT?.trim()
      || "https://api.github.com/user/emails",
  }
}

function readLegacyOidcProviderConfig(
  request?: NextRequest,
): OidcProviderConfig | null {
  const issuer = process.env.ORBIT_DASHBOARD_OIDC_ISSUER_URL?.trim() ?? ""
  const clientId = process.env.ORBIT_DASHBOARD_OIDC_CLIENT_ID?.trim() ?? ""
  const clientSecret = process.env.ORBIT_DASHBOARD_OIDC_CLIENT_SECRET?.trim() ?? ""
  if (!issuer && !clientId && !clientSecret) {
    return null
  }
  return {
    id: "sso",
    label: "Continue with SSO",
    protocol: "oidc",
    issuer,
    clientId,
    clientSecret,
    scopes: readScopeEnv("ORBIT_DASHBOARD_OIDC_SCOPES", ["openid", "profile", "email"]),
    redirectUri: process.env.ORBIT_DASHBOARD_OIDC_REDIRECT_URI?.trim() || resolveSharedRedirectUri(request),
    prompt: process.env.ORBIT_DASHBOARD_OIDC_PROMPT?.trim(),
    tenantClaimKeys: readTenantClaimKeys("ORBIT_DASHBOARD_OIDC_TENANT_CLAIMS"),
  }
}

function resolveSharedRedirectUri(request?: NextRequest): string | undefined {
  const configured = process.env.ORBIT_DASHBOARD_OIDC_REDIRECT_URI?.trim()
  if (configured) {
    return configured
  }
  if (!request) {
    return undefined
  }
  return `${request.nextUrl.origin}/api/dashboard/auth/oidc/callback`
}

function readScopeEnv(envName: string, fallback: string[]): string[] {
  const raw = process.env[envName]?.trim()
  if (!raw) {
    return fallback
  }
  return normalizeScopes(raw.split(/\s+/))
}

function readTenantClaimKeys(envName: string): string[] {
  const providerSpecific = process.env[envName]?.trim()
  if (providerSpecific) {
    return providerSpecific
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean)
  }
  const shared = process.env.ORBIT_DASHBOARD_OIDC_TENANT_CLAIMS?.trim()
  if (!shared) {
    return []
  }
  return shared
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean)
}

function requireProviderEndpoint(value: string | undefined, label: string): string {
  const normalized = normalizeClaimValue(value)
  if (!normalized) {
    throw new Error(`OAuth provider configuration missing ${label}.`)
  }
  return normalized
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

function extractRequestOrigin(originHeader: string, refererHeader: string): string {
  const originFromHeader = normalizeOrigin(originHeader)
  if (originFromHeader) {
    return originFromHeader
  }
  return normalizeOrigin(refererHeader)
}

function normalizeOrigin(value: string): string {
  const normalized = value.trim()
  if (!normalized) {
    return ""
  }
  try {
    return new URL(normalized).origin
  } catch {
    return ""
  }
}

function readAllowMissingOriginForMutations(): boolean {
  return readEnvFlag("ORBIT_DASHBOARD_ALLOW_MISSING_ORIGIN", false)
}

function readAllowUnsignedIdTokenFallback(): boolean {
  return readEnvFlag("ORBIT_DASHBOARD_OIDC_ALLOW_UNSIGNED_ID_TOKEN_FALLBACK", false)
}

function readEnvFlag(name: string, fallback: boolean): boolean {
  const raw = process.env[name]?.trim().toLowerCase()
  if (!raw) {
    return fallback
  }
  if (raw === "1" || raw === "true" || raw === "yes" || raw === "on") {
    return true
  }
  if (raw === "0" || raw === "false" || raw === "no" || raw === "off") {
    return false
  }
  return fallback
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
