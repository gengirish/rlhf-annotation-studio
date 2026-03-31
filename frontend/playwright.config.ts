import { defineConfig } from "@playwright/test";

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
  webServer: process.env.E2E_BASE_URL
    ? undefined
    : {
        command: "npx next dev -p 3456",
        url: "http://localhost:3456",
        reuseExistingServer: true
      }
});
