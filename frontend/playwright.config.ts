import { defineConfig } from "@playwright/test";
import dotenv from "dotenv";
import path from "path";

// Next's dev server reads .env.local itself, but the Playwright process does
// not — without this the Clerk keys and E2E credentials are missing from setup.
dotenv.config({ path: path.join(__dirname, ".env.local") });

const STORAGE_STATE = path.join(__dirname, ".auth/user.json");

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: true,
  timeout: 60_000,
  retries: process.env.CI ? 1 : 0,
  reporter: "html",
  use: {
    baseURL: process.env.E2E_BASE_URL || "http://localhost:3456",
    trace: "on-first-retry",
    screenshot: "only-on-failure"
  },
  projects: [
    // Signs in once with Clerk; the main project reuses the saved session.
    { name: "setup", testMatch: /global\.setup\.ts/ },
    {
      name: "e2e",
      dependencies: ["setup"],
      use: { storageState: STORAGE_STATE },
      // Signed-out behaviour is covered separately, without a stored session.
      testIgnore: [/auth-flows\.spec\.ts/, /global\.setup\.ts/]
    },
    {
      name: "signed-out",
      testMatch: /auth-flows\.spec\.ts/,
      use: { storageState: { cookies: [], origins: [] } }
    }
  ],
  webServer: process.env.E2E_BASE_URL
    ? undefined
    : {
        command: "npx next dev -p 3456",
        url: "http://localhost:3456",
        reuseExistingServer: true,
        // Next reads .env.local itself; the Clerk keys must be there or
        // clerkMiddleware throws "Missing secretKey" and every route 500s.
        timeout: 120_000
      }
});
