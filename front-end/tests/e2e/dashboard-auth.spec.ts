import { expect, test, type Page } from "@playwright/test"

type DashboardMode = "password" | "oidc" | "disabled"

test("password login unlocks dashboard and supports create flow", async ({ page }) => {
  let authenticated = false
  const keys = [
    {
      key_id: "key_1",
      name: "Primary",
      key_prefix: "orbit_pk_aaaa1111",
      scopes: ["read", "write", "feedback", "keys:read", "keys:write"],
      status: "active",
      created_at: "2026-02-20T10:00:00Z",
      last_used_at: null,
      last_used_source: null,
      revoked_at: null,
    },
  ]
  await mockDashboardApi(page, {
    mode: "password",
    getAuthenticated: () => authenticated,
    onLogin: async () => {
      authenticated = true
    },
    onListKeys: async () => ({
      data: keys,
      cursor: null,
      has_more: false,
    }),
    onCreateKey: async () => ({
      ...keys[0],
      key_id: "key_created",
      name: "Production key",
      key: "orbit_pk_visible_once_secret",
    }),
    onRotateKey: async () => ({
      revoked_key_id: "key_1",
      new_key: {
        ...keys[0],
        key_id: "key_rotated",
        name: "Primary Rotated",
        key: "orbit_pk_rotated_once_secret",
      },
    }),
    onRevokeKey: async () => ({
      key_id: "key_1",
      revoked: true,
      revoked_at: "2026-02-21T11:00:00Z",
    }),
  })

  await page.goto("/dashboard")
  await expect(page.getByText("Dashboard Sign-In")).toBeVisible()
  await page.getByPlaceholder("Dashboard password").fill("super-secret")
  await page.getByRole("button", { name: "Sign in" }).click()

  await expect(page.getByText("API Keys", { exact: true })).toBeVisible()
  await page.getByRole("button", { name: "Create key" }).click()
  await page.getByRole("button", { name: "Create key" }).last().click()
  await expect(page.getByText("Copy this key now")).toBeVisible()
  await expect(page.getByText("orbit_pk_visible_once_secret")).toBeVisible()
})

test("OIDC mode shows Google and GitHub login paths", async ({ page }) => {
  await mockDashboardApi(page, {
    mode: "oidc",
    getAuthenticated: () => false,
    oidcProviders: [
      { id: "google", label: "Continue with Google", path: "/api/dashboard/auth/oidc/start?provider=google" },
      { id: "github", label: "Continue with GitHub", path: "/api/dashboard/auth/oidc/start?provider=github" },
    ],
    onListKeys: async () => ({ data: [], cursor: null, has_more: false }),
    onCreateKey: async () => {
      throw new Error("unused")
    },
    onRotateKey: async () => {
      throw new Error("unused")
    },
    onRevokeKey: async () => {
      throw new Error("unused")
    },
  })

  let navigatedToOidc = false
  await page.route("**/api/dashboard/auth/oidc/start?provider=google", async (route) => {
    navigatedToOidc = true
    await route.fulfill({
      status: 307,
      headers: {
        location: "/dashboard?auth_error=oidc_provider_error",
      },
    })
  })

  await page.goto("/dashboard")
  await expect(page.getByRole("button", { name: "Continue with Google" })).toBeVisible()
  await expect(page.getByRole("button", { name: "Continue with GitHub" })).toBeVisible()
  await page.getByRole("button", { name: "Continue with Google" }).click()
  await expect.poll(() => navigatedToOidc).toBeTruthy()
})

test("session expiry falls back to sign-in state", async ({ page }) => {
  await mockDashboardApi(page, {
    mode: "password",
    getAuthenticated: () => true,
    onListKeys: async () => {
      throw new Error("401")
    },
    onCreateKey: async () => {
      throw new Error("unused")
    },
    onRotateKey: async () => {
      throw new Error("unused")
    },
    onRevokeKey: async () => {
      throw new Error("unused")
    },
  })

  await page.goto("/dashboard")
  await expect(page.getByText("Dashboard session expired. Sign in again.")).toBeVisible()
  await expect(page.getByText("Dashboard Sign-In")).toBeVisible()
})

async function mockDashboardApi(
  page: Page,
  options: {
    mode: DashboardMode
    getAuthenticated: () => boolean
    oidcProviders?: Array<{ id: string; label: string; path: string }>
    onLogin?: () => Promise<void>
    onListKeys: () => Promise<{ data: unknown[]; cursor: string | null; has_more: boolean }>
    onCreateKey: () => Promise<unknown>
    onRotateKey: () => Promise<unknown>
    onRevokeKey: () => Promise<unknown>
  },
): Promise<void> {
  await page.route("**/api/dashboard/auth/session", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        authenticated: options.getAuthenticated(),
        mode: options.mode,
        oidc_login_path: "/api/dashboard/auth/oidc/start",
        oidc_login_providers: options.mode === "oidc"
          ? (
            options.oidcProviders
            ?? [{ id: "sso", label: "Continue with SSO", path: "/api/dashboard/auth/oidc/start" }]
          )
          : undefined,
      }),
    })
  })

  await page.route("**/api/dashboard/auth/login", async (route) => {
    if (!options.onLogin) {
      await route.fulfill({
        status: 400,
        contentType: "application/json",
        body: JSON.stringify({ detail: "login not available" }),
      })
      return
    }
    await options.onLogin()
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        authenticated: true,
        mode: "password",
        subject: "dashboard-user",
      }),
    })
  })

  await page.route("**/api/dashboard/auth/logout", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        authenticated: false,
        mode: options.mode,
      }),
    })
  })

  await page.route("**/api/dashboard/keys?*", async (route) => {
    if (!options.getAuthenticated()) {
      await route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({ detail: "auth required" }),
      })
      return
    }
    try {
      const payload = await options.onListKeys()
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(payload),
      })
    } catch (error) {
      await route.fulfill({
        status: String(error).includes("401") ? 401 : 500,
        contentType: "application/json",
        body: JSON.stringify({ detail: "failed to list keys" }),
      })
    }
  })

  await page.route("**/api/dashboard/keys", async (route) => {
    if (route.request().method() !== "POST") {
      await route.fallback()
      return
    }
    if (!options.getAuthenticated()) {
      await route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({ detail: "auth required" }),
      })
      return
    }
    await route.fulfill({
      status: 201,
      contentType: "application/json",
      body: JSON.stringify(await options.onCreateKey()),
    })
  })

  await page.route("**/api/dashboard/keys/*/rotate", async (route) => {
    if (!options.getAuthenticated()) {
      await route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({ detail: "auth required" }),
      })
      return
    }
    await route.fulfill({
      status: 201,
      contentType: "application/json",
      body: JSON.stringify(await options.onRotateKey()),
    })
  })

  await page.route("**/api/dashboard/keys/*/revoke", async (route) => {
    if (!options.getAuthenticated()) {
      await route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({ detail: "auth required" }),
      })
      return
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(await options.onRevokeKey()),
    })
  })
}
