"use client"

import { useEffect, useMemo, useState } from "react"
import {
  AlertCircle,
  CheckCircle2,
  Copy,
  LogOut,
  RefreshCcw,
  ShieldCheck,
  ShieldOff,
} from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  DASHBOARD_DEFAULT_SCOPES,
  DASHBOARD_SCOPE_OPTIONS,
  OrbitApiKeyIssueResponse,
  OrbitApiKeySummary,
  OrbitDashboardApiError,
  OrbitDashboardClient,
  OrbitDashboardSessionResponse,
  OrbitMetadataSummary,
  OrbitStatusResponse,
  OrbitTenantMetricsResponse,
} from "@/lib/orbit-dashboard"

const PAGE_SIZE = 10

type AuthState = "checking" | "signed_out" | "signed_in"
type OidcLoginProvider = NonNullable<OrbitDashboardSessionResponse["oidc_login_providers"]>[number]

export function DashboardConsole() {
  const client = useMemo(() => new OrbitDashboardClient(), [])

  const [authState, setAuthState] = useState<AuthState>("checking")
  const [authMode, setAuthMode] = useState<OrbitDashboardSessionResponse["mode"]>("password")
  const [oidcLoginPath, setOidcLoginPath] = useState("/api/dashboard/auth/oidc/start")
  const [oidcProviders, setOidcProviders] = useState<OidcLoginProvider[]>([])
  const [authPassword, setAuthPassword] = useState("")
  const [authError, setAuthError] = useState<string | null>(null)
  const [isSigningIn, setIsSigningIn] = useState(false)
  const [isSigningOut, setIsSigningOut] = useState(false)

  const [keys, setKeys] = useState<OrbitApiKeySummary[]>([])
  const [accountStatus, setAccountStatus] = useState<OrbitStatusResponse | null>(null)
  const [tenantMetrics, setTenantMetrics] = useState<OrbitTenantMetricsResponse | null>(null)
  const [metadataSummary, setMetadataSummary] = useState<OrbitMetadataSummary | null>(null)
  const [metricsText, setMetricsText] = useState("")
  const [loadingMetrics, setLoadingMetrics] = useState(false)
  const [metricsError, setMetricsError] = useState<string | null>(null)
  const [loadingStatus, setLoadingStatus] = useState(false)
  const [statusError, setStatusError] = useState<string | null>(null)
  const [loadingTenantMetrics, setLoadingTenantMetrics] = useState(false)
  const [tenantMetricsError, setTenantMetricsError] = useState<string | null>(null)
  const [loadingKeys, setLoadingKeys] = useState(false)
  const [requestError, setRequestError] = useState<string | null>(null)
  const [statusMessage, setStatusMessage] = useState<string | null>(null)
  const [statusTone, setStatusTone] = useState<"success" | "error" | "info">("info")

  const [cursorStack, setCursorStack] = useState<Array<string | null>>([null])
  const [nextCursor, setNextCursor] = useState<string | null>(null)
  const [hasMore, setHasMore] = useState(false)
  const [reloadTick, setReloadTick] = useState(0)

  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false)
  const [createName, setCreateName] = useState("Production key")
  const [createScopes, setCreateScopes] = useState<string[]>([...DASHBOARD_DEFAULT_SCOPES])
  const [isCreating, setIsCreating] = useState(false)
  const [isRequestingPilotPro, setIsRequestingPilotPro] = useState(false)

  const [revokeTarget, setRevokeTarget] = useState<OrbitApiKeySummary | null>(null)
  const [isRevoking, setIsRevoking] = useState(false)

  const [rotateTarget, setRotateTarget] = useState<OrbitApiKeySummary | null>(null)
  const [rotateName, setRotateName] = useState("")
  const [rotateScopes, setRotateScopes] = useState<string[]>([])
  const [rotateConfirmed, setRotateConfirmed] = useState(false)
  const [isRotating, setIsRotating] = useState(false)

  const [revealedKey, setRevealedKey] = useState<OrbitApiKeyIssueResponse | null>(null)
  const [copyState, setCopyState] = useState<"idle" | "copied" | "failed">("idle")

  const currentCursor = cursorStack[cursorStack.length - 1] ?? null

  useEffect(() => {
    let isCancelled = false
    const loadSession = async () => {
      try {
        const session = await client.getSession()
        if (isCancelled) {
          return
        }
        applySession(session)
        setAuthError(null)
      } catch (error) {
        if (isCancelled) {
          return
        }
        setAuthState("signed_out")
        setAuthError(readErrorMessage(error))
      }
    }
    void loadSession()
    return () => {
      isCancelled = true
    }
  }, [client])

  useEffect(() => {
    if (typeof window === "undefined") {
      return
    }
    const authErrorCode = new URLSearchParams(window.location.search)
      .get("auth_error")
      ?.trim()
    if (!authErrorCode) {
      return
    }
    setAuthError(describeAuthError(authErrorCode))
  }, [])

  useEffect(() => {
    if (authState !== "signed_in") {
      setAccountStatus(null)
      setMetadataSummary(null)
      setLoadingStatus(false)
      setStatusError(null)
      return
    }

    let isCancelled = false
    const loadStatus = async () => {
      setLoadingStatus(true)
      setStatusError(null)
      try {
        const response = await client.getStatus()
        if (isCancelled) {
          return
        }
        setAccountStatus(response)
        setMetadataSummary(response.metadata_summary ?? null)
      } catch (error) {
        if (isCancelled) {
          return
        }
        if (isUnauthorized(error)) {
          setAuthState("signed_out")
          setAuthError("Dashboard session expired. Sign in again.")
          setAccountStatus(null)
          setStatusError(null)
          return
        }
        setAccountStatus(null)
        setStatusError(readErrorMessage(error))
      } finally {
        if (!isCancelled) {
          setLoadingStatus(false)
        }
      }
    }
    void loadStatus()
    return () => {
      isCancelled = true
    }
  }, [authState, client, reloadTick])

  useEffect(() => {
    if (authState !== "signed_in") {
      setTenantMetrics(null)
      setLoadingTenantMetrics(false)
      setTenantMetricsError(null)
      return
    }

    let isCancelled = false
    const loadTenantMetrics = async () => {
      setLoadingTenantMetrics(true)
      setTenantMetricsError(null)
      try {
        const response = await client.getTenantMetrics()
        if (isCancelled) {
          return
        }
        setTenantMetrics(response)
      } catch (error) {
        if (isCancelled) {
          return
        }
        if (isUnauthorized(error)) {
          setAuthState("signed_out")
          setAuthError("Dashboard session expired. Sign in again.")
          setTenantMetrics(null)
          setTenantMetricsError(null)
          return
        }
        setTenantMetrics(null)
        setTenantMetricsError(readErrorMessage(error))
      } finally {
        if (!isCancelled) {
          setLoadingTenantMetrics(false)
        }
      }
    }
    void loadTenantMetrics()
    return () => {
      isCancelled = true
    }
  }, [authState, client, reloadTick])

  useEffect(() => {
    if (authState !== "signed_in") {
      setMetricsText("")
      setLoadingMetrics(false)
      setMetricsError(null)
      return
    }

    let isCancelled = false
    const loadMetrics = async () => {
      setLoadingMetrics(true)
      setMetricsError(null)
      try {
        const response = await client.getMetricsText()
        if (isCancelled) {
          return
        }
        setMetricsText(response)
      } catch (error) {
        if (isCancelled) {
          return
        }
        if (isUnauthorized(error)) {
          setAuthState("signed_out")
          setAuthError("Dashboard session expired. Sign in again.")
          setMetricsText("")
          setMetricsError(null)
          return
        }
        setMetricsText("")
        setMetricsError(readErrorMessage(error))
      } finally {
        if (!isCancelled) {
          setLoadingMetrics(false)
        }
      }
    }
    void loadMetrics()
    return () => {
      isCancelled = true
    }
  }, [authState, client, reloadTick])

  useEffect(() => {
    if (authState !== "signed_in") {
      setKeys([])
      setHasMore(false)
      setNextCursor(null)
      setLoadingKeys(false)
      setRequestError(null)
      return
    }

    let isCancelled = false
    const load = async () => {
      setLoadingKeys(true)
      setRequestError(null)
      try {
        const response = await client.listApiKeys({
          limit: PAGE_SIZE,
          cursor: currentCursor,
        })
        if (isCancelled) {
          return
        }
        setKeys(response.data)
        setHasMore(response.has_more)
        setNextCursor(response.cursor)
      } catch (error) {
        if (isCancelled) {
          return
        }
        if (isUnauthorized(error)) {
          setAuthState("signed_out")
          setAuthError("Dashboard session expired. Sign in again.")
          setKeys([])
          setHasMore(false)
          setNextCursor(null)
          setRequestError(null)
          return
        }
        setKeys([])
        setHasMore(false)
        setNextCursor(null)
        setRequestError(readErrorMessage(error))
      } finally {
        if (!isCancelled) {
          setLoadingKeys(false)
        }
      }
    }
    void load()
    return () => {
      isCancelled = true
    }
  }, [authState, client, currentCursor, reloadTick])

  const refreshCurrentPage = () => {
    setReloadTick((value) => value + 1)
  }

  const refreshFirstPage = () => {
    setCursorStack([null])
    setReloadTick((value) => value + 1)
  }

  const applySession = (session: OrbitDashboardSessionResponse) => {
    setAuthMode(session.mode)
    const resolvedProviders = (session.oidc_login_providers ?? []).filter(
      (item): item is OidcLoginProvider => Boolean(item?.id && item?.label && item?.path),
    )
    if (resolvedProviders.length > 0) {
      setOidcProviders(resolvedProviders)
      setOidcLoginPath(resolvedProviders[0].path)
    } else {
      setOidcProviders([])
    }
    if (session.oidc_login_path) {
      setOidcLoginPath(session.oidc_login_path)
    }
    setAuthState(session.authenticated ? "signed_in" : "signed_out")
  }

  const handleOidcSignIn = (path: string) => {
    setAuthError(null)
    window.location.assign(path)
  }

  const handleSignIn = async () => {
    if (authMode === "disabled") {
      setAuthState("signed_in")
      setAuthError(null)
      refreshFirstPage()
      return
    }
    if (authMode === "oidc") {
      const defaultProviderPath = oidcProviders[0]?.path || oidcLoginPath || "/api/dashboard/auth/oidc/start"
      handleOidcSignIn(defaultProviderPath)
      return
    }

    const normalizedPassword = authPassword.trim()
    if (!normalizedPassword) {
      setAuthError("Password is required.")
      return
    }

    setIsSigningIn(true)
    setAuthError(null)
    try {
      const session = await client.login(normalizedPassword)
      applySession(session)
      if (!session.authenticated) {
        setAuthError("Dashboard authentication failed.")
        return
      }
      setAuthPassword("")
      setStatusTone("success")
      setStatusMessage("Dashboard session established.")
      refreshFirstPage()
    } catch (error) {
      setAuthState("signed_out")
      setAuthError(readErrorMessage(error))
    } finally {
      setIsSigningIn(false)
    }
  }

  const handleSignOut = async () => {
    setIsSigningOut(true)
    setAuthError(null)
    try {
      const session = await client.logout()
      applySession(session)
      setStatusTone("info")
      setStatusMessage("Dashboard session ended.")
      setKeys([])
      setCursorStack([null])
      setHasMore(false)
      setNextCursor(null)
      setRequestError(null)
      setAccountStatus(null)
      setStatusError(null)
      setTenantMetrics(null)
      setTenantMetricsError(null)
      setMetricsText("")
      setMetricsError(null)
      setIsRequestingPilotPro(false)
    } catch (error) {
      setAuthError(readErrorMessage(error))
    } finally {
      setIsSigningOut(false)
    }
  }

  const handleCreateKey = async () => {
    const normalizedName = createName.trim()
    if (!normalizedName) {
      setStatusTone("error")
      setStatusMessage("Key name is required.")
      return
    }
    setIsCreating(true)
    try {
      const issued = await client.createApiKey({
        name: normalizedName,
        scopes: createScopes,
      })
      setRevealedKey(issued)
      setCopyState("idle")
      setIsCreateDialogOpen(false)
      setCreateName("Production key")
      setCreateScopes([...DASHBOARD_DEFAULT_SCOPES])
      setStatusTone("success")
      setStatusMessage(`Issued key "${issued.name}". Copy it now, it will not be shown again.`)
      refreshFirstPage()
    } catch (error) {
      if (isUnauthorized(error)) {
        setAuthState("signed_out")
        setAuthError("Dashboard session expired. Sign in again.")
        return
      }
      setStatusTone("error")
      setStatusMessage(readErrorMessage(error))
    } finally {
      setIsCreating(false)
    }
  }

  const handleRevokeKey = async () => {
    if (!revokeTarget) {
      return
    }
    setIsRevoking(true)
    try {
      await client.revokeApiKey(revokeTarget.key_id)
      setStatusTone("success")
      setStatusMessage(`Revoked key "${revokeTarget.name}".`)
      setRevokeTarget(null)
      refreshCurrentPage()
    } catch (error) {
      if (isUnauthorized(error)) {
        setAuthState("signed_out")
        setAuthError("Dashboard session expired. Sign in again.")
        return
      }
      setStatusTone("error")
      setStatusMessage(readErrorMessage(error))
    } finally {
      setIsRevoking(false)
    }
  }

  const openRotateDialog = (target: OrbitApiKeySummary) => {
    setRotateTarget(target)
    setRotateName(target.name)
    setRotateScopes(target.scopes.length > 0 ? [...target.scopes] : [...DASHBOARD_DEFAULT_SCOPES])
    setRotateConfirmed(false)
  }

  const handleRotateKey = async () => {
    if (!rotateTarget) {
      return
    }
    if (!rotateConfirmed) {
      setStatusTone("error")
      setStatusMessage("Confirm rotation before proceeding.")
      return
    }
    setIsRotating(true)
    try {
      const normalizedRotateName = rotateName.trim()
      const rotated = await client.rotateApiKey(rotateTarget.key_id, {
        ...(normalizedRotateName ? { name: normalizedRotateName } : {}),
        ...(rotateScopes.length > 0 ? { scopes: rotateScopes } : {}),
      })
      setRevealedKey(rotated.new_key)
      setCopyState("idle")
      setStatusTone("success")
      setStatusMessage(
        `Rotated key "${rotateTarget.name}". Old key was revoked and a new key is ready to copy.`,
      )
      setRotateTarget(null)
      refreshCurrentPage()
    } catch (error) {
      if (isUnauthorized(error)) {
        setAuthState("signed_out")
        setAuthError("Dashboard session expired. Sign in again.")
        return
      }
      setStatusTone("error")
      setStatusMessage(readErrorMessage(error))
    } finally {
      setIsRotating(false)
    }
  }

  const handleCopyRevealedKey = async () => {
    if (!revealedKey) {
      return
    }
    try {
      await navigator.clipboard.writeText(revealedKey.key)
      setCopyState("copied")
    } catch {
      setCopyState("failed")
    }
  }

  const handlePilotProRequest = async () => {
    if (!usageSummary || usageSummary.pilotProRequested || isRequestingPilotPro) {
      return
    }
    setIsRequestingPilotPro(true)
    try {
      const result = await client.requestPilotPro()
      setStatusTone("success")
      setStatusMessage(
        result.email_sent
          ? "Pilot Pro request sent. We'll follow up by email."
          : "Pilot Pro request saved. We will follow up shortly.",
      )
      refreshCurrentPage()
    } catch (error) {
      if (isUnauthorized(error)) {
        setAuthState("signed_out")
        setAuthError("Dashboard session expired. Sign in again.")
        return
      }
      setStatusTone("error")
      setStatusMessage(readErrorMessage(error))
    } finally {
      setIsRequestingPilotPro(false)
    }
  }

  const toggleCreateScope = (scope: string, checked: boolean) => {
    setCreateScopes((current) => {
      if (checked) {
        return uniqueScopes([...current, scope])
      }
      return current.filter((item) => item !== scope)
    })
  }

  const toggleRotateScope = (scope: string, checked: boolean) => {
    setRotateScopes((current) => {
      if (checked) {
        return uniqueScopes([...current, scope])
      }
      return current.filter((item) => item !== scope)
    })
  }

  const goToNextPage = () => {
    if (!nextCursor) {
      return
    }
    setCursorStack((current) => [...current, nextCursor])
  }

  const goToPreviousPage = () => {
    setCursorStack((current) => {
      if (current.length <= 1) {
        return current
      }
      return current.slice(0, -1)
    })
  }

  const isAuthenticated = authState === "signed_in"
  const usageSummary = tenantMetrics
    ? deriveUsageSummary(tenantMetrics)
    : accountStatus
      ? deriveUsageSummaryFromStatus(accountStatus, keys)
      : null
  const usageAlerts = usageSummary ? buildUsageAlerts(usageSummary) : []
  const metadataAlerts = metadataSummary ? buildMetadataAlerts(metadataSummary) : []
  const metricsSnapshot = useMemo(
    () => parsePrometheusMetrics(metricsText),
    [metricsText],
  )

  return (
    <div className="space-y-8">
      <Card>
        <CardHeader>
          <CardTitle>Connection</CardTitle>
          <CardDescription>
            Browser requests use <code className="text-primary">/api/dashboard/*</code> server routes. Authentication and upstream API access are handled server-side.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex flex-wrap items-center gap-3">
            <span
              className={`inline-flex items-center gap-2 border px-2.5 py-1 text-xs ${
                isAuthenticated ? "border-primary/30 text-primary" : "border-border text-muted-foreground"
              }`}
            >
              {isAuthenticated ? <ShieldCheck className="h-3.5 w-3.5" /> : <ShieldOff className="h-3.5 w-3.5" />}
              {authState === "checking" ? "Checking session..." : isAuthenticated ? "Signed in" : "Signed out"}
            </span>
            {isAuthenticated && authMode !== "disabled" && (
              <Button size="sm" variant="outline" onClick={handleSignOut} disabled={isSigningOut}>
                <LogOut className="h-4 w-4" />
                {isSigningOut ? "Signing out..." : "Sign out"}
              </Button>
            )}
          </div>
          <p className="text-xs text-muted-foreground">
            No Orbit Bearer token is stored in localStorage or exposed to client-side JavaScript.
          </p>
          <p className="text-xs text-muted-foreground">
            Security-sensitive configuration remains server-only and is never sent to the browser.
          </p>
        </CardContent>
      </Card>

      {authState !== "signed_in" && (
        <Card>
          <CardHeader>
            <CardTitle>Dashboard Sign-In</CardTitle>
            <CardDescription>
              API key management is locked behind a server-issued session cookie.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {authMode === "password" ? (
              <>
                <Input
                  type="password"
                  value={authPassword}
                  onChange={(event) => setAuthPassword(event.target.value)}
                  placeholder="Dashboard password"
                  autoComplete="current-password"
                />
                <Button onClick={handleSignIn} disabled={isSigningIn || authState === "checking"}>
                  {isSigningIn ? "Signing in..." : "Sign in"}
                </Button>
              </>
            ) : authMode === "oidc" ? (
              <>
                <p className="text-xs text-muted-foreground">
                  Sign in with your OIDC identity provider. Orbit mints tenant-scoped short-lived JWTs server-side.
                </p>
                <div className="flex flex-wrap gap-3">
                  {(oidcProviders.length > 0
                    ? oidcProviders
                    : [{ id: "sso", label: "Continue with SSO", path: oidcLoginPath }]
                  ).map((provider) => (
                    <Button
                      key={provider.id}
                      onClick={() => handleOidcSignIn(provider.path)}
                      disabled={authState === "checking"}
                    >
                      {provider.label}
                    </Button>
                  ))}
                </div>
              </>
            ) : (
              <div className="border border-border bg-secondary/20 p-3 text-xs text-muted-foreground">
                Dashboard auth mode is disabled. This should only be used in local development.
              </div>
            )}
            {authError && (
              <div className="border border-destructive/40 bg-destructive/10 p-3 text-xs text-destructive">
                {authError}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {statusMessage && (
        <div
          className={`flex items-start gap-3 border p-4 text-sm ${
            statusTone === "error"
              ? "border-destructive/40 bg-destructive/10 text-destructive"
              : statusTone === "success"
                ? "border-primary/30 bg-primary/5 text-foreground"
                : "border-border bg-secondary/30 text-foreground"
          }`}
        >
          {statusTone === "error" ? (
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          ) : (
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />
          )}
          <span>{statusMessage}</span>
        </div>
      )}

      {isAuthenticated && (
        <Card id="usage-breakdown">
          <CardHeader>
            <CardTitle>Usage & Plan</CardTitle>
            <CardDescription>
              {usageSummary
                ? `Current plan: ${usageSummary.planLabel}`
                : "Usage summary for your active account."}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {(loadingStatus || loadingTenantMetrics) && (
              <div className="border border-border bg-secondary/20 p-3 text-xs text-muted-foreground">
                Loading usage metrics...
              </div>
            )}
            {tenantMetricsError && (
              <div className="border border-destructive/40 bg-destructive/10 p-3 text-xs text-destructive">
                {tenantMetricsError}
              </div>
            )}
            {!loadingStatus && !loadingTenantMetrics && !tenantMetricsError && usageSummary && (
              <>
                <div className="border border-border bg-secondary/20 p-3">
                  <div className="text-sm font-medium text-foreground">
                    Current plan: {usageSummary.planLabel}
                  </div>
                  <div className="mt-2 text-xs text-muted-foreground">
                    Ingest: {formatCount(usageSummary.ingestUsed)}/{formatCount(usageSummary.ingestLimit)} | Retrieve:{" "}
                    {formatCount(usageSummary.retrieveUsed)}/{formatCount(usageSummary.retrieveLimit)}
                  </div>
                  <div className="mt-1 text-xs text-muted-foreground">
                    Active keys: {formatCount(usageSummary.activeApiKeys)}/{formatCount(usageSummary.apiKeyLimit)} | Resets{" "}
                    {usageSummary.resetAtLabel}
                  </div>
                  {usageSummary.pilotProRequested && (
                    <div className="mt-1 text-xs text-primary">
                      Pilot Pro request sent
                      {usageSummary.pilotProRequestedAtLabel
                        ? ` on ${usageSummary.pilotProRequestedAtLabel}`
                        : ""}
                      .
                    </div>
                  )}
                </div>

                {usageAlerts.map((alert) => (
                  <div
                    key={alert.id}
                    className={`border p-3 text-sm ${
                      alert.tone === "limit"
                        ? "border-destructive/40 bg-destructive/10 text-destructive"
                        : alert.tone === "critical"
                          ? "border-amber-500/40 bg-amber-500/10 text-amber-700"
                          : "border-primary/30 bg-primary/5 text-foreground"
                    }`}
                  >
                    <div className="font-medium">{alert.title}</div>
                    <div className="mt-1 text-xs opacity-90">{alert.body}</div>
                    <div className="mt-3 flex flex-wrap gap-2">
                      <Button
                        size="sm"
                        onClick={handlePilotProRequest}
                        disabled={usageSummary.pilotProRequested || isRequestingPilotPro}
                      >
                        {usageSummary.pilotProRequested
                          ? "Request sent"
                          : isRequestingPilotPro
                            ? "Sending..."
                            : "Request Pilot Pro"}
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => {
                          document
                            .getElementById("usage-breakdown")
                            ?.scrollIntoView({ behavior: "smooth", block: "start" })
                        }}
                      >
                        View usage
                      </Button>
                    </div>
                  </div>
                ))}
              </>
            )}
          </CardContent>
        </Card>
      )}

      {isAuthenticated && metadataSummary && (
        <Card id="metadata-breakdown">
          <CardHeader>
            <CardTitle>Memory metadata</CardTitle>
            <CardDescription>
              Fact inference counts from <code className="text-primary">/v1/status</code> metadata_summary.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {metadataAlerts.map((alert) => (
              <div
                key={alert.id}
                className={`border p-3 text-sm ${
                  alert.tone === "warning"
                    ? "border-amber-500/40 bg-amber-500/10 text-amber-700"
                    : alert.tone === "critical"
                      ? "border-destructive/40 bg-destructive/10 text-destructive"
                      : "border-primary/30 bg-primary/5 text-foreground"
                }`}
              >
                <div className="font-medium">{alert.title}</div>
                <div className="mt-1 text-xs opacity-90">{alert.body}</div>
              </div>
            ))}
            <div className="grid grid-cols-2 gap-3 text-xs text-muted-foreground md:grid-cols-4">
              <div>
                <div className="text-[11px] uppercase tracking-[0.3em]">Inferred facts</div>
                <div className="text-lg font-semibold text-foreground">
                  {formatCount(metadataSummary.total_inferred_facts)}
                </div>
              </div>
              <div>
                <div className="text-[11px] uppercase tracking-[0.3em]">Confirmed</div>
                <div className="text-lg font-semibold text-foreground">
                  {formatCount(metadataSummary.confirmed_facts)}
                </div>
              </div>
              <div>
                <div className="text-[11px] uppercase tracking-[0.3em]">Contested</div>
                <div className="text-lg font-semibold text-foreground">
                  {formatCount(metadataSummary.contested_facts)}
                </div>
              </div>
              <div>
                <div className="text-[11px] uppercase tracking-[0.3em]">Conflict guards</div>
                <div className="text-lg font-semibold text-foreground">
                  {formatCount(metadataSummary.conflict_guards)}
                </div>
              </div>
              <div>
                <div className="text-[11px] uppercase tracking-[0.3em]">Contested ratio</div>
                <div className="text-lg font-semibold text-foreground">
                  {formatPercent(metadataSummary.contested_ratio)}
                </div>
              </div>
              <div>
                <div className="text-[11px] uppercase tracking-[0.3em]">Guard ratio</div>
                <div className="text-lg font-semibold text-foreground">
                  {formatPercent(metadataSummary.conflict_guard_ratio)}
                </div>
              </div>
              <div className="md:col-span-2">
                <div className="text-[11px] uppercase tracking-[0.3em]">Avg fact age</div>
                <div className="text-lg font-semibold text-foreground">
                  {metadataSummary.average_fact_age_days.toFixed(1)} days
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {isAuthenticated && (
        <Card id="metrics-overview">
          <CardHeader>
            <CardTitle>Runtime Metrics</CardTitle>
            <CardDescription>
              Live Prometheus counters from Orbit API via secure dashboard proxy.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {loadingMetrics && (
              <div className="border border-border bg-secondary/20 p-3 text-xs text-muted-foreground">
                Loading metrics...
              </div>
            )}
            {metricsError && (
              <div className="border border-destructive/40 bg-destructive/10 p-3 text-xs text-destructive">
                {metricsError}
              </div>
            )}
            {!loadingMetrics && !metricsError && metricsText.trim() && (
              <>
                <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                  <MetricTile
                    label="Ingest Requests"
                    value={formatCount(metricsSnapshot.ingestRequestsTotal)}
                  />
                  <MetricTile
                    label="Retrieve Requests"
                    value={formatCount(metricsSnapshot.retrieveRequestsTotal)}
                  />
                  <MetricTile
                    label="Feedback Requests"
                    value={formatCount(metricsSnapshot.feedbackRequestsTotal)}
                  />
                  <MetricTile
                    label="Uptime"
                    value={formatDurationSeconds(metricsSnapshot.uptimeSeconds)}
                  />
                  <MetricTile
                    label="Dashboard Auth Failures"
                    value={formatCount(metricsSnapshot.dashboardAuthFailuresTotal)}
                  />
                  <MetricTile
                    label="Key Rotation Failures"
                    value={formatCount(metricsSnapshot.dashboardKeyRotationFailuresTotal)}
                  />
                </div>
                <div className="border border-border bg-secondary/20 p-3 text-xs text-muted-foreground">
                  Flash pipeline metrics are platform health signals from the shared ingest runtime
                  (queue depth, drops, failures). Usage and key quotas above remain tenant scoped.
                </div>
                <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
                  <MetricTile
                    label="Flash Mode"
                    value={metricsSnapshot.flashPipelineModeAsync > 0 ? "Async" : "Sync"}
                  />
                  <MetricTile
                    label="Flash Workers"
                    value={formatCount(metricsSnapshot.flashPipelineWorkers)}
                  />
                  <MetricTile
                    label="Flash Queue Depth"
                    value={`${formatCount(metricsSnapshot.flashPipelineQueueDepth)} / ${formatCount(metricsSnapshot.flashPipelineQueueCapacity)}`}
                  />
                  <MetricTile
                    label="Flash Runs"
                    value={formatCount(metricsSnapshot.flashPipelineRunsTotal)}
                  />
                  <MetricTile
                    label="Flash Maintenance"
                    value={formatCount(metricsSnapshot.flashPipelineMaintenanceTotal)}
                  />
                  <MetricTile
                    label="Flash Drops"
                    value={formatCount(metricsSnapshot.flashPipelineDroppedTotal)}
                  />
                  <MetricTile
                    label="Flash Failures"
                    value={formatCount(metricsSnapshot.flashPipelineFailuresTotal)}
                  />
                </div>
                <details className="border border-border bg-secondary/20 p-3 text-xs text-muted-foreground">
                  <summary className="cursor-pointer font-medium text-foreground">
                    Show raw Prometheus payload
                  </summary>
                  <pre className="mt-3 whitespace-pre-wrap break-all">
                    {metricsText}
                  </pre>
                </details>
              </>
            )}
          </CardContent>
        </Card>
      )}

      {isAuthenticated && revealedKey && (
        <Card className="border-primary/30 bg-primary/5">
          <CardHeader>
            <CardTitle>Copy this key now</CardTitle>
            <CardDescription>
              Orbit shows plaintext key material once. After you hide this panel, the secret cannot be recovered.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="border border-border bg-background p-3">
              <code className="break-all text-xs text-primary">{revealedKey.key}</code>
            </div>
            <div className="flex flex-wrap gap-3">
              <Button onClick={handleCopyRevealedKey}>
                <Copy className="h-4 w-4" />
                {copyState === "copied" ? "Copied" : "Copy key"}
              </Button>
              <Button variant="outline" onClick={() => setRevealedKey(null)}>
                I copied it, hide key
              </Button>
              {copyState === "failed" && (
                <span className="text-xs text-destructive self-center">
                  Clipboard copy failed. Copy manually before hiding.
                </span>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {isAuthenticated && (
        <Card>
          <CardHeader>
            <CardTitle>API Keys</CardTitle>
            <CardDescription>
              Create, rotate, and revoke keys. Keep only active keys you actually use.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-wrap items-center gap-3">
              <Button onClick={() => setIsCreateDialogOpen(true)}>
                Create key
              </Button>
              <Button variant="outline" onClick={refreshCurrentPage} disabled={loadingKeys}>
                <RefreshCcw className={`h-4 w-4 ${loadingKeys ? "animate-spin" : ""}`} />
                Refresh
              </Button>
              <span className="text-xs text-muted-foreground">
                Page {cursorStack.length}
              </span>
            </div>

            {requestError && (
              <div className="border border-destructive/40 bg-destructive/10 p-3 text-xs text-destructive">
                {requestError}
              </div>
            )}

            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Prefix</TableHead>
                  <TableHead>Scopes</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead>Last used</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {loadingKeys && (
                  <TableRow>
                    <TableCell colSpan={7} className="text-center text-muted-foreground">
                      Loading keys...
                    </TableCell>
                  </TableRow>
                )}
                {!loadingKeys && keys.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={7} className="text-center text-muted-foreground">
                      No keys found for this account.
                    </TableCell>
                  </TableRow>
                )}
                {!loadingKeys &&
                  keys.map((item) => (
                    <TableRow key={item.key_id}>
                      <TableCell className="font-medium">{item.name}</TableCell>
                      <TableCell>
                        <code className="text-xs text-primary">{item.key_prefix}</code>
                      </TableCell>
                      <TableCell className="max-w-[220px] whitespace-normal text-xs text-muted-foreground">
                        {item.scopes.join(", ")}
                      </TableCell>
                      <TableCell>
                        <span className={item.status === "active" ? "text-primary" : "text-muted-foreground"}>
                          {item.status}
                        </span>
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        {formatDate(item.created_at)}
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        {item.last_used_at
                          ? `${formatDate(item.last_used_at)}${
                              item.last_used_source ? ` (${item.last_used_source})` : ""
                            }`
                          : "Never"}
                      </TableCell>
                      <TableCell>
                        <div className="flex gap-2">
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => openRotateDialog(item)}
                            disabled={item.status !== "active"}
                          >
                            Rotate
                          </Button>
                          <Button
                            size="sm"
                            variant="destructive"
                            onClick={() => setRevokeTarget(item)}
                            disabled={item.status !== "active"}
                          >
                            Revoke
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
              </TableBody>
            </Table>

            <div className="flex items-center justify-between">
              <Button
                variant="outline"
                onClick={goToPreviousPage}
                disabled={cursorStack.length <= 1 || loadingKeys}
              >
                Previous
              </Button>
              <span className="text-xs text-muted-foreground">
                Showing up to {PAGE_SIZE} keys
              </span>
              <Button
                variant="outline"
                onClick={goToNextPage}
                disabled={!hasMore || !nextCursor || loadingKeys}
              >
                Next
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      <Dialog
        open={isCreateDialogOpen}
        onOpenChange={(open) => {
          if (!isCreating) {
            setIsCreateDialogOpen(open)
          }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create API key</DialogTitle>
            <DialogDescription>
              Give this key a name and scopes. Keep scopes narrow for production usage.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <Input
              value={createName}
              onChange={(event) => setCreateName(event.target.value)}
              placeholder="Key name"
            />
            <div className="space-y-2">
              {DASHBOARD_SCOPE_OPTIONS.map((scope) => {
                const checked = createScopes.includes(scope)
                return (
                  <label key={scope} className="flex items-center gap-3 text-sm text-foreground">
                    <Checkbox
                      checked={checked}
                      onCheckedChange={(value) => toggleCreateScope(scope, value === true)}
                    />
                    <span>{scope}</span>
                  </label>
                )
              })}
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsCreateDialogOpen(false)} disabled={isCreating}>
              Cancel
            </Button>
            <Button onClick={handleCreateKey} disabled={isCreating}>
              {isCreating ? "Creating..." : "Create key"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={revokeTarget !== null}
        onOpenChange={(open) => {
          if (!open && !isRevoking) {
            setRevokeTarget(null)
          }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Revoke key</DialogTitle>
            <DialogDescription>
              This action is immediate. Clients using this key will get 401 responses.
            </DialogDescription>
          </DialogHeader>
          <div className="border border-border bg-secondary/20 p-3 text-sm text-muted-foreground">
            <div>Name: <span className="text-foreground">{revokeTarget?.name}</span></div>
            <div>Prefix: <code className="text-primary">{revokeTarget?.key_prefix}</code></div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setRevokeTarget(null)} disabled={isRevoking}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleRevokeKey} disabled={isRevoking}>
              {isRevoking ? "Revoking..." : "Confirm revoke"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={rotateTarget !== null}
        onOpenChange={(open) => {
          if (!open && !isRotating) {
            setRotateTarget(null)
            setRotateConfirmed(false)
          }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Rotate key</DialogTitle>
            <DialogDescription>
              Rotation revokes the current key and issues a new one in a single operation.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <Input
              value={rotateName}
              onChange={(event) => setRotateName(event.target.value)}
              placeholder="New key name"
            />
            <div className="space-y-2">
              {DASHBOARD_SCOPE_OPTIONS.map((scope) => {
                const checked = rotateScopes.includes(scope)
                return (
                  <label key={scope} className="flex items-center gap-3 text-sm text-foreground">
                    <Checkbox
                      checked={checked}
                      onCheckedChange={(value) => toggleRotateScope(scope, value === true)}
                    />
                    <span>{scope}</span>
                  </label>
                )
              })}
            </div>
            <label className="flex items-start gap-3 text-sm text-muted-foreground">
              <Checkbox
                checked={rotateConfirmed}
                onCheckedChange={(value) => setRotateConfirmed(value === true)}
              />
              <span>I understand the old key will stop working immediately after rotation.</span>
            </label>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setRotateTarget(null)} disabled={isRotating}>
              Cancel
            </Button>
            <Button onClick={handleRotateKey} disabled={isRotating || !rotateConfirmed}>
              {isRotating ? "Rotating..." : "Confirm rotate"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

type PrometheusSnapshot = {
  ingestRequestsTotal: number
  retrieveRequestsTotal: number
  feedbackRequestsTotal: number
  dashboardAuthFailuresTotal: number
  dashboardKeyRotationFailuresTotal: number
  uptimeSeconds: number
  flashPipelineModeAsync: number
  flashPipelineWorkers: number
  flashPipelineQueueDepth: number
  flashPipelineQueueCapacity: number
  flashPipelineDroppedTotal: number
  flashPipelineFailuresTotal: number
  flashPipelineRunsTotal: number
  flashPipelineMaintenanceTotal: number
}

function MetricTile(props: { label: string; value: string }) {
  const { label, value } = props
  return (
    <div className="border border-border bg-secondary/20 p-3">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-1 text-base font-medium text-foreground">{value}</div>
    </div>
  )
}

function parsePrometheusMetrics(metricsText: string): PrometheusSnapshot {
  return {
    ingestRequestsTotal: parsePrometheusMetricValue(metricsText, "orbit_ingest_requests_total"),
    retrieveRequestsTotal: parsePrometheusMetricValue(metricsText, "orbit_retrieve_requests_total"),
    feedbackRequestsTotal: parsePrometheusMetricValue(metricsText, "orbit_feedback_requests_total"),
    dashboardAuthFailuresTotal: parsePrometheusMetricValue(
      metricsText,
      "orbit_dashboard_auth_failures_total",
    ),
    dashboardKeyRotationFailuresTotal: parsePrometheusMetricValue(
      metricsText,
      "orbit_dashboard_key_rotation_failures_total",
    ),
    uptimeSeconds: parsePrometheusMetricValue(metricsText, "orbit_uptime_seconds"),
    flashPipelineModeAsync: parsePrometheusMetricValue(
      metricsText,
      "orbit_flash_pipeline_mode_async",
    ),
    flashPipelineWorkers: parsePrometheusMetricValue(
      metricsText,
      "orbit_flash_pipeline_workers",
    ),
    flashPipelineQueueDepth: parsePrometheusMetricValue(
      metricsText,
      "orbit_flash_pipeline_queue_depth",
    ),
    flashPipelineQueueCapacity: parsePrometheusMetricValue(
      metricsText,
      "orbit_flash_pipeline_queue_capacity",
    ),
    flashPipelineDroppedTotal: parsePrometheusMetricValue(
      metricsText,
      "orbit_flash_pipeline_dropped_total",
    ),
    flashPipelineFailuresTotal: parsePrometheusMetricValue(
      metricsText,
      "orbit_flash_pipeline_failures_total",
    ),
    flashPipelineRunsTotal: parsePrometheusMetricValue(
      metricsText,
      "orbit_flash_pipeline_runs_total",
    ),
    flashPipelineMaintenanceTotal: parsePrometheusMetricValue(
      metricsText,
      "orbit_flash_pipeline_maintenance_total",
    ),
  }
}

function parsePrometheusMetricValue(metricsText: string, metricName: string): number {
  const escapedName = metricName.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")
  const matcher = new RegExp(`^${escapedName}(?:\\{[^}]*\\})?\\s+([0-9]+(?:\\.[0-9]+)?)$`, "m")
  const match = metricsText.match(matcher)
  if (!match) {
    return 0
  }
  const value = Number.parseFloat(match[1])
  if (!Number.isFinite(value)) {
    return 0
  }
  return value
}

function isUnauthorized(error: unknown): boolean {
  return error instanceof OrbitDashboardApiError && error.status === 401
}

function readErrorMessage(error: unknown): string {
  if (error instanceof OrbitDashboardApiError) {
    const code = error.code?.trim().toLowerCase()
    if (code === "quota_ingest_monthly_exceeded") {
      return "Monthly ingest limit reached on Free. New events are blocked until monthly reset. Request Pilot Pro for higher limits."
    }
    if (code === "quota_retrieve_monthly_exceeded") {
      return "Monthly retrieval limit reached on Free. Retrieval is blocked until monthly reset. Request Pilot Pro for higher limits."
    }
    if (code === "quota_api_keys_exceeded") {
      return "API key limit reached for this plan. Revoke an unused key or request Pilot Pro."
    }
    if (code === "rate_limit_exceeded") {
      return "Too many requests. Retry after the current rate-limit window resets."
    }
    if (code === "dashboard_proxy_upstream_unreachable") {
      return error.message
    }
    return error.message
  }
  if (error instanceof Error) {
    return error.message
  }
  return "Unexpected request failure."
}

type UsageSummary = {
  planLabel: string
  planCode: string
  ingestUsed: number
  ingestLimit: number
  retrieveUsed: number
  retrieveLimit: number
  activeApiKeys: number
  apiKeyLimit: number
  resetAtIso: string | null
  resetAtLabel: string
  warningThresholdPercent: number
  criticalThresholdPercent: number
  pilotProRequested: boolean
  pilotProRequestStatus: string
  pilotProRequestedAtLabel: string | null
}

type UsageAlert = {
  id: string
  tone: "warning" | "critical" | "limit"
  title: string
  body: string
}

type MetadataAlert = {
  id: string
  tone: "info" | "warning" | "critical"
  title: string
  body: string
}

function deriveUsageSummary(
  metrics: OrbitTenantMetricsResponse,
): UsageSummary {
  const planCode = normalizeOptionalString(metrics.plan)?.toLowerCase() || "free"
  const planLabel = planCode === "pilot_pro" ? "Pilot Pro" : "Free"
  const resetAtIso = normalizeOptionalString(metrics.reset_at)
  const pilotProRequestedAtIso = normalizeOptionalString(metrics.pilot_pro_requested_at)
  return {
    planLabel,
    planCode,
    ingestUsed: sanitizeCount(metrics.ingest.used),
    ingestLimit: resolveLimit(metrics.ingest.limit, 0),
    retrieveUsed: sanitizeCount(metrics.retrieve.used),
    retrieveLimit: resolveLimit(metrics.retrieve.limit, 0),
    activeApiKeys: sanitizeCount(metrics.api_keys.used),
    apiKeyLimit: resolveLimit(metrics.api_keys.limit, defaultApiKeyLimitForPlan(planCode)),
    resetAtIso,
    resetAtLabel: resetAtIso ? formatDate(resetAtIso) : "next month (UTC)",
    warningThresholdPercent: sanitizePercent(metrics.warning_threshold_percent, 80),
    criticalThresholdPercent: sanitizePercent(metrics.critical_threshold_percent, 95),
    pilotProRequested: Boolean(metrics.pilot_pro_requested),
    pilotProRequestStatus: metrics.pilot_pro_requested ? "requested" : "not_requested",
    pilotProRequestedAtLabel: pilotProRequestedAtIso ? formatDate(pilotProRequestedAtIso) : null,
  }
}

function deriveUsageSummaryFromStatus(
  status: OrbitStatusResponse,
  keys: OrbitApiKeySummary[],
): UsageSummary {
  const quota = status.account_usage.quota
  const planCode = (quota.plan ?? "free").trim().toLowerCase() || "free"
  const planLabel = planCode === "pilot_pro" ? "Pilot Pro" : "Free"
  const ingestLimit = resolveMonthlyLimit(quota.events_per_month, quota.events_per_day)
  const retrieveLimit = resolveMonthlyLimit(quota.queries_per_month, quota.queries_per_day)
  const apiKeyLimit = resolveLimit(
    quota.api_keys,
    defaultApiKeyLimitForPlan(planCode),
  )
  const activeApiKeysFromStatus = sanitizeCount(status.account_usage.active_api_keys ?? 0)
  const activeApiKeysFromList = keys.filter((item) => item.status === "active").length
  const resetAtIso = normalizeOptionalString(quota.reset_at)
  const pilotProRequestStatus =
    normalizeOptionalString(status.pilot_pro_request?.status)?.toLowerCase() || "not_requested"
  const pilotProRequestedAtIso = normalizeOptionalString(status.pilot_pro_request?.requested_at)
  return {
    planLabel,
    planCode,
    ingestUsed: sanitizeCount(status.account_usage.events_ingested_this_month),
    ingestLimit,
    retrieveUsed: sanitizeCount(status.account_usage.queries_this_month),
    retrieveLimit,
    activeApiKeys: Math.max(activeApiKeysFromStatus, activeApiKeysFromList),
    apiKeyLimit,
    resetAtIso,
    resetAtLabel: resetAtIso ? formatDate(resetAtIso) : "next month (UTC)",
    warningThresholdPercent: sanitizePercent(quota.warning_threshold_percent, 80),
    criticalThresholdPercent: sanitizePercent(quota.critical_threshold_percent, 95),
    pilotProRequested: pilotProRequestStatus === "requested",
    pilotProRequestStatus,
    pilotProRequestedAtLabel: pilotProRequestedAtIso ? formatDate(pilotProRequestedAtIso) : null,
  }
}

function buildUsageAlerts(summary: UsageSummary): UsageAlert[] {
  const alerts: UsageAlert[] = []
  alerts.push(...buildResourceAlerts({
    key: "ingest",
    label: "ingest quota",
    planLabel: summary.planLabel,
    used: summary.ingestUsed,
    limit: summary.ingestLimit,
    warningThresholdPercent: summary.warningThresholdPercent,
    criticalThresholdPercent: summary.criticalThresholdPercent,
    resetAtLabel: summary.resetAtLabel,
  }))
  alerts.push(...buildResourceAlerts({
    key: "retrieve",
    label: "retrieval quota",
    planLabel: summary.planLabel,
    used: summary.retrieveUsed,
    limit: summary.retrieveLimit,
    warningThresholdPercent: summary.warningThresholdPercent,
    criticalThresholdPercent: summary.criticalThresholdPercent,
    resetAtLabel: summary.resetAtLabel,
  }))
  if (summary.apiKeyLimit > 0 && summary.activeApiKeys >= summary.apiKeyLimit) {
    alerts.push({
      id: "api-keys-limit",
      tone: "limit",
      title: "API key limit reached",
      body: `This plan includes up to ${formatCount(summary.apiKeyLimit)} API keys. Revoke an unused key or request Pilot Pro.`,
    })
  }
  return alerts
}

function buildMetadataAlerts(summary: OrbitMetadataSummary): MetadataAlert[] {
  const alerts: MetadataAlert[] = []
  if (summary.total_inferred_facts === 0) {
    alerts.push({
      id: "metadata-none",
      tone: "info",
      title: "No inferred facts yet",
      body: "Interact with Orbit a few times so metadata_summary can start ranking contested vs confirmed facts.",
    })
    return alerts
  }
  if (summary.contested_ratio >= 0.3) {
    alerts.push({
      id: "metadata-contested-high",
      tone: "warning",
      title: "Contested facts are rising",
      body: `Approximately ${formatPercent(summary.contested_ratio)} of inferred facts need clarification. Ask follow-up questions to confirm states.`,
    })
  } else if (summary.contested_ratio <= 0.05) {
    alerts.push({
      id: "metadata-contested-low",
      tone: "info",
      title: "Low contested rate",
      body: "Most inferred facts are confirmed—keep the same flows to maintain clarity.",
    })
  }
  if (summary.conflict_guards > 0) {
    alerts.push({
      id: "metadata-conflict-guards",
      tone: "info",
      title: "Conflict guards detected",
      body: `${formatCount(summary.conflict_guards)} guards flagged to avoid mistaken memories. Ask clarifying questions when they appear.`,
    })
  }
  return alerts
}

function buildResourceAlerts(input: {
  key: string
  label: string
  planLabel: string
  used: number
  limit: number
  warningThresholdPercent: number
  criticalThresholdPercent: number
  resetAtLabel: string
}): UsageAlert[] {
  if (input.limit <= 0) {
    return []
  }
  const percent = (input.used / input.limit) * 100
  if (input.used >= input.limit) {
    return [
      {
        id: `${input.key}-limit`,
        tone: "limit",
        title: `Monthly ${input.label} reached`,
        body: `Requests are blocked on ${input.planLabel} until ${input.resetAtLabel}. Request Pilot Pro for higher limits.`,
      },
    ]
  }
  if (percent >= input.criticalThresholdPercent) {
    return [
      {
        id: `${input.key}-critical`,
        tone: "critical",
        title: `Heads up: ${input.label} almost exhausted`,
        body: `Only ${formatCount(input.limit - input.used)} requests left this month on ${input.planLabel}.`,
      },
    ]
  }
  if (percent >= input.warningThresholdPercent) {
    return [
      {
        id: `${input.key}-warning`,
        tone: "warning",
        title: `You're at ${Math.round(percent)}% of your monthly ${input.label}`,
        body: `You're close to the ${input.planLabel} limit. Request Pilot Pro now to avoid interruptions.`,
      },
    ]
  }
  return []
}

function resolveLimit(primary: number | null | undefined, fallback: number): number {
  const primaryNumber = sanitizeCount(primary ?? 0)
  if (primaryNumber > 0) {
    return primaryNumber
  }
  return sanitizeCount(fallback)
}

function resolveMonthlyLimit(
  monthly: number | null | undefined,
  daily: number,
): number {
  const monthlyLimit = sanitizeCount(monthly ?? 0)
  if (monthlyLimit > 0) {
    return monthlyLimit
  }
  const dailyLimit = sanitizeCount(daily)
  if (dailyLimit <= 0) {
    return 0
  }
  return dailyLimit * 30
}

function defaultApiKeyLimitForPlan(planCode: string): number {
  if (planCode === "pilot_pro") {
    return 25
  }
  return 3
}

function sanitizeCount(value: number): number {
  if (!Number.isFinite(value)) {
    return 0
  }
  return Math.max(0, Math.floor(value))
}

function sanitizePercent(value: number | null | undefined, fallback: number): number {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return fallback
  }
  const normalized = Math.floor(value)
  if (normalized < 1 || normalized > 100) {
    return fallback
  }
  return normalized
}

function normalizeOptionalString(value: string | null | undefined): string | null {
  if (typeof value !== "string") {
    return null
  }
  const normalized = value.trim()
  return normalized.length > 0 ? normalized : null
}

function formatCount(value: number): string {
  return sanitizeCount(value).toLocaleString()
}

function formatDurationSeconds(value: number): string {
  const totalSeconds = sanitizeCount(value)
  const days = Math.floor(totalSeconds / 86400)
  const hours = Math.floor((totalSeconds % 86400) / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  if (days > 0) {
    return `${days}d ${hours}h`
  }
  if (hours > 0) {
    return `${hours}h ${minutes}m`
  }
  return `${minutes}m`
}

function formatPercent(value: number): string {
  const normalized = Math.round(value * 100)
  return `${normalized}%`
}

function uniqueScopes(scopes: string[]): string[] {
  return Array.from(new Set(scopes))
}

function formatDate(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.valueOf())) {
    return value
  }
  return date.toLocaleString()
}

function describeAuthError(code: string): string {
  const normalized = code.trim().toLowerCase()
  if (normalized === "oidc_provider_error") {
    return "OIDC provider returned an authentication error."
  }
  if (normalized === "oidc_state_invalid") {
    return "OIDC state validation failed. Retry login."
  }
  if (normalized === "oidc_exchange_failed") {
    return "Failed to exchange OIDC authorization code."
  }
  if (normalized === "oidc_disabled") {
    return "OIDC login path was called while OIDC mode is disabled."
  }
  if (normalized === "oidc_config_invalid") {
    return "OIDC provider configuration is incomplete or invalid."
  }
  return "Authentication flow failed. Retry sign-in."
}

