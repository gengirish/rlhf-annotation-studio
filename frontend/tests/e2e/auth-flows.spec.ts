import { expect, test } from "@playwright/test";

/**
 * Signed-out behaviour of the Clerk integration.
 *
 * Runs in the "signed-out" Playwright project, which deliberately has no stored
 * session — every other spec reuses the session from global.setup.ts.
 *
 * These cover regressions that actually shipped during the Clerk migration:
 *  - protected routes returned 404 instead of prompting a sign-in
 *  - the landing page always showed "Login", even when signed in
 *  - the retired /auth route had to keep working for old links
 */

const PROTECTED_ROUTES = [
  "/dashboard",
  "/analytics",
  "/reviews",
  "/settings",
  "/team",
  "/quality",
  "/datasets",
  "/audit",
  "/webhooks",
  "/exams",
  "/certificates",
  "/course",
  "/author",
  "/auto-reviews"
];

test.describe("Signed out — route protection", () => {
  for (const route of PROTECTED_ROUTES) {
    test(`${route} sends a signed-out visitor to sign-in, not 404`, async ({ page }) => {
      const response = await page.goto(route);

      // Regression guard: auth.protect() used to render notFound() here, which
      // reads as a broken link rather than "please sign in".
      expect(response?.status(), `${route} should not 404`).not.toBe(404);
      await expect(page).toHaveURL(/sign-in|clerk/, { timeout: 20_000 });
    });
  }
});

test.describe("Signed out — public routes stay reachable", () => {
  test("landing page renders without auth", async ({ page }) => {
    const response = await page.goto("/");
    expect(response?.status()).toBe(200);
    await expect(page).not.toHaveURL(/sign-in/);
  });

  test("landing page offers sign-in and sign-up, not the retired /auth form", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("link", { name: "Login" })).toHaveAttribute("href", /\/sign-in/);
    await expect(page.getByRole("link", { name: "Get Started" })).toHaveAttribute(
      "href",
      /\/sign-up/
    );
    // "Go to Dashboard" is the signed-in variant and must not show here.
    await expect(page.getByRole("link", { name: "Go to Dashboard" })).toHaveCount(0);
  });

  test("sign-in page renders the Clerk widget", async ({ page }) => {
    const response = await page.goto("/sign-in");
    expect(response?.status()).toBe(200);
    await expect(page.locator("form, .cl-rootBox, [data-clerk-component]").first()).toBeVisible({
      timeout: 20_000
    });
  });

  test("sign-up page renders", async ({ page }) => {
    const response = await page.goto("/sign-up");
    expect(response?.status()).toBe(200);
  });

  test("legacy /auth redirects to sign-in for old links and bookmarks", async ({ page }) => {
    await page.goto("/auth");
    await expect(page).toHaveURL(/\/sign-in/, { timeout: 20_000 });
  });

  test("robots.txt keeps authenticated routes out of search indexes", async ({ page }) => {
    const response = await page.goto("/robots.txt");
    expect(response?.status()).toBe(200);
    const body = await response!.text();
    // Mirrors the protected prefixes; /certificate/ (public) must stay crawlable.
    expect(body).toContain("Disallow: /dashboard/");
    expect(body).toContain("Disallow: /exams/");
    expect(body).not.toContain("Disallow: /certificate/");
  });
});

test.describe("Signed out — security headers", () => {
  test("responses carry the hardening headers", async ({ page }) => {
    // "load" can abort when Clerk's dev handshake redirects mid-navigation.
    const response = await page.goto("/", { waitUntil: "domcontentloaded" });
    const headers = response!.headers();
    expect(headers["x-frame-options"]).toBe("DENY");
    expect(headers["x-content-type-options"]).toBe("nosniff");
    expect(headers["referrer-policy"]).toBe("strict-origin-when-cross-origin");
    // Framework version must not be advertised.
    expect(headers["x-powered-by"]).toBeUndefined();
  });
});
