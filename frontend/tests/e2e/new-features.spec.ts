import { expect, test, type Page } from "@playwright/test";

const MOCK_AUTH_ADMIN = {
  token: "fake-token-admin",
  annotator: {
    id: "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    name: "Admin User",
    email: "admin@example.com",
    phone: null,
    role: "admin",
    org_id: "org-001"
  },
  session_id: "b2c3d4e5-f6a7-8901-bcde-f12345678901"
};

async function mockBaseRoutes(page: Page) {
  await page.route("**/**/api/v1/auth/login", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(MOCK_AUTH_ADMIN) });
  });
  await page.route("**/**/api/v1/sessions/*/workspace/**", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ revisions: [] }) });
  });
  await page.route("**/**/api/v1/sessions/*/workspace", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200, contentType: "application/json",
        body: JSON.stringify({ session_id: MOCK_AUTH_ADMIN.session_id, annotator_id: MOCK_AUTH_ADMIN.annotator.id, tasks: [], annotations: {}, task_times: {}, active_pack_file: null })
      });
      return;
    }
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ok: true, annotation_warnings: [] }) });
  });
  await page.route("**/**/api/v1/tasks/**", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ packs: [], total: 0 }) });
  });
  await page.route("**/**/api/v1/metrics/**", async (route) => {
    await route.fulfill({
      status: 200, contentType: "application/json",
      body: JSON.stringify({ total_tasks: 0, completed_tasks: 0, skipped_tasks: 0, pending_tasks: 0, completion_rate: 0, avg_time_seconds: 0, median_time_seconds: 0, total_time_seconds: 0, dimension_averages: {}, tasks_by_type: {} })
    });
  });
  await page.route("**/**/api/v1/reviews/**", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) });
  });
  await page.route("**/**/api/v1/orgs/**", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ id: "org-001", name: "Test Org" }) });
  });
  await page.route("**/**/api/v1/inference/**", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ default: "test-model", models: [] }) });
  });
}

async function loginAsAdmin(page: Page) {
  await mockBaseRoutes(page);
  await page.goto("/auth");
  await page.getByPlaceholder("Email").fill("admin@example.com");
  await page.getByPlaceholder(/Password/).fill("password123");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/dashboard/, { timeout: 15000 });
}

test.describe("Quality page", () => {
  test("loads and shows heading", async ({ page }) => {
    await loginAsAdmin(page);
    await page.route("**/**/api/v1/quality/**", async (route) => {
      const url = route.request().url();
      if (url.includes("leaderboard")) {
        await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ annotators: [], computed_at: new Date().toISOString() }) });
      } else if (url.includes("dashboard")) {
        await route.fulfill({
          status: 200, contentType: "application/json",
          body: JSON.stringify({ leaderboard: { annotators: [], computed_at: new Date().toISOString() }, drift_alerts: [], org_average_trust: 0, total_annotators: 0, calibration_pass_rate: null })
        });
      } else {
        await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({}) });
      }
    });
    await page.route("**/**/api/v1/quality/calibration", async (route) => {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) });
    });
    await page.goto("/quality");
    await expect(page.getByText(/quality/i).first()).toBeVisible({ timeout: 15000 });
  });
});

test.describe("Datasets page", () => {
  test("loads and shows heading", async ({ page }) => {
    await loginAsAdmin(page);
    await page.route("**/**/api/v1/datasets**", async (route) => {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ items: [], total: 0, skip: 0, limit: 50 }) });
    });
    await page.goto("/datasets");
    await expect(page.getByText(/dataset/i).first()).toBeVisible({ timeout: 15000 });
  });
});

test.describe("Webhooks page", () => {
  test("loads and shows heading", async ({ page }) => {
    await loginAsAdmin(page);
    await page.route("**/**/api/v1/webhooks**", async (route) => {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) });
    });
    await page.goto("/webhooks");
    await expect(page.getByText(/webhook/i).first()).toBeVisible({ timeout: 15000 });
  });
});

test.describe("Audit page", () => {
  test("loads and shows heading", async ({ page }) => {
    await loginAsAdmin(page);
    await page.route("**/**/api/v1/audit/**", async (route) => {
      const url = route.request().url();
      if (url.includes("stats")) {
        await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ last_24h: {}, last_7d: {}, last_30d: {} }) });
      } else {
        await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ items: [], total: 0, skip: 0, limit: 50 }) });
      }
    });
    await page.goto("/audit");
    await expect(page.getByText(/audit/i).first()).toBeVisible({ timeout: 15000 });
  });
});
