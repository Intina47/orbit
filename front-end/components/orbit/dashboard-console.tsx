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
  getOrbitApiBaseUrl,
} from "@/lib/orbit-dashboard"

const PAGE_SIZE = 10

type AuthState = "checking" | "signed_out" | "signed_in"
type OidcLoginProvider = NonNullable<OrbitDashboardSessionResponse["oidc_login_providers"]>[number]

export function DashboardConsole() {
  const apiBaseUrl = getOrbitApiBaseUrl()
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

  return (
    <div className="space-y-8">
      <Card>
        <CardHeader>
          <CardTitle>Connection</CardTitle>
          <CardDescription>
            Browser requests go to <code className="text-primary">/api/dashboard/*</code>. The server proxy exchanges your dashboard session for short-lived Orbit JWTs and forwards to{" "}
            <code className="text-primary">{apiBaseUrl}</code>.
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
            Required server envs: <code className="text-primary">ORBIT_DASHBOARD_SESSION_SECRET</code>,{" "}
            <code className="text-primary">ORBIT_DASHBOARD_ORBIT_JWT_SECRET</code>, and auth mode variables
            (<code className="text-primary">ORBIT_DASHBOARD_AUTH_MODE</code> + password or OIDC config).
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

function isUnauthorized(error: unknown): boolean {
  return error instanceof OrbitDashboardApiError && error.status === 401
}

function readErrorMessage(error: unknown): string {
  if (error instanceof OrbitDashboardApiError) {
    return error.message
  }
  if (error instanceof Error) {
    return error.message
  }
  return "Unexpected request failure."
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
