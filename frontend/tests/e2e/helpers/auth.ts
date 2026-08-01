import { expect, type Page } from "@playwright/test";

/**
 * Shared entry point for tests that need to be "signed in".
 *
 * Authentication itself comes from the stored Clerk session created by
 * `global.setup.ts` — `clerkMiddleware` runs server-side, so a real session is
 * required and cannot be faked with route mocks.
 *
 * The *identity* the app displays still comes from `/api/v1/auth/me`, so mocking
 * that lets one Clerk account stand in for annotator, reviewer and admin without
 * needing three real users.
 */

export interface MockAuth {
  token: string;
  annotator: {
    id: string;
    name: string;
    email: string;
    phone: string | null;
    role: string;
    org_id: string | null;
  };
  session_id: string;
}

/** Serve `/auth/me` so ClerkSessionBridge can populate the store. */
export async function mockMe(page: Page, auth: MockAuth) {
  await page.route("**/**/api/v1/auth/me", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ annotator: auth.annotator, session_id: auth.session_id })
    });
  });
}

/**
 * Replaces the old "fill the login form" flow. Call after the spec's own
 * `mockAllRoutes`, since Playwright matches the most recently added route first.
 */
export async function enterApp(page: Page, auth: MockAuth, target = "/dashboard") {
  await mockMe(page, auth);
  await page.goto(target);
  await expect(page).not.toHaveURL(/sign-in/, { timeout: 20_000 });
  await waitForSession(page);
}

/**
 * Blocks until ClerkSessionBridge has written the session into the store.
 *
 * The old login flow set this synchronously from the login response, so specs
 * could act immediately. Clerk populates it asynchronously from `/auth/me`, and
 * without this wait tests click controls that have not rendered yet.
 */
export async function waitForSession(page: Page) {
  await expect
    .poll(
      async () => {
        const raw = await page.evaluate(() => localStorage.getItem("rlhf-next-store"));
        if (!raw) return false;
        try {
          const parsed = JSON.parse(raw) as { state?: { sessionId?: string | null } };
          return Boolean(parsed?.state?.sessionId);
        } catch {
          return false;
        }
      },
      { timeout: 20_000, message: "session never reached the store via /auth/me" }
    )
    .toBe(true);
}

/**
 * Seeds localStorage for the app origin, then loads the target page.
 * Some specs need a key present *before* the page reads it on mount.
 */
export async function enterAppWithLocalStorage(
  page: Page,
  auth: MockAuth,
  entries: Record<string, string>,
  target = "/dashboard"
) {
  await mockMe(page, auth);
  // Establish the origin first — localStorage is unavailable on about:blank.
  await page.goto(target);
  await page.evaluate((kv) => {
    for (const [k, v] of Object.entries(kv)) localStorage.setItem(k, v);
  }, entries);
  await page.reload();
  await expect(page).not.toHaveURL(/sign-in/, { timeout: 20_000 });
  await waitForSession(page);
}
