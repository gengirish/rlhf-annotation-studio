import { clerk, clerkSetup } from "@clerk/testing/playwright";
import { test as setup, expect } from "@playwright/test";
import path from "path";

/**
 * Signs in one dedicated Clerk user and saves the browser state, so the ~150
 * specs reuse a single real session instead of authenticating individually.
 *
 * A real session is needed because `clerkMiddleware` enforces auth server-side —
 * mocking API responses alone cannot get past it. Roles are still controlled
 * per-test by mocking `/api/v1/auth/me`, so this one account covers admin,
 * reviewer and annotator scenarios.
 */

export const STORAGE_STATE = path.join(__dirname, "../../.auth/user.json");

setup("authenticate once with Clerk", async ({ page }) => {
  const identifier = process.env.E2E_CLERK_USER;

  if (!identifier) {
    throw new Error(
      "E2E_CLERK_USER must be set in frontend/.env.local (or CI secrets), and must be " +
        "a Clerk test address ending in +clerk_test@example.com. Create one with:\n" +
        "  cd backend && python scripts/create_e2e_clerk_user.py"
    );
  }

  await clerkSetup();

  // Must land on an unprotected page that loads Clerk first. The landing page
  // qualifies; /sign-in does not, because the mounted SignIn component competes
  // with the programmatic sign-in.
  await page.goto("/");
  await clerk.loaded({ page });

  // This instance enables password as an attribute but NOT as a first factor
  // (email_address is the only one), so `strategy: "password"` fails silently.
  // email_code works because the account uses a +clerk_test address, for which
  // Clerk accepts a fixed verification code without sending mail.
  await clerk.signIn({ page, signInParams: { strategy: "email_code", identifier } });

  // Prove the session is real rather than trusting signIn's return — a failed
  // sign-in here is silent, leaving every downstream spec to fail confusingly.
  const clientUser = await page.evaluate(() => {
    const c = (window as unknown as { Clerk?: { user?: { id: string } | null } }).Clerk;
    return c?.user?.id ?? null;
  });
  expect(clientUser, "Clerk sign-in did not establish a user session").not.toBeNull();

  await page.goto("/dashboard");
  await expect(page).not.toHaveURL(/sign-in/, { timeout: 20_000 });

  await page.context().storageState({ path: STORAGE_STATE });
});
