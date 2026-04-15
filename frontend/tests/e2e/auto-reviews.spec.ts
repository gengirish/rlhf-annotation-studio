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

const MOCK_AUTH_ANNOTATOR = {
  token: "fake-token",
  annotator: {
    id: "f5f5432e-57cd-4b22-84df-a35395f60529",
    name: "E2E User",
    email: "e2e@example.com",
    phone: null,
    role: "annotator",
    org_id: null
  },
  session_id: "4b94db28-59c6-4716-a890-1c7e58eca66d"
};

const MOCK_PACK = {
  id: "pack-1",
  slug: "debugging-exercises-python",
  name: "Python Debugging",
  description: "Debug Python snippets",
  language: "python",
  task_count: 2,
  created_at: "2026-01-01T00:00:00Z"
};

const MOCK_EVALUATIONS = {
  items: [
    {
      id: "eval-1",
      task_pack_id: "pack-1",
      task_id: "task-1",
      judge_model: "gpt-4o",
      evaluation_json: {
        preference: 1,
        reasoning: "Response A provides a more thorough explanation with better error handling.",
        dimensions: { clarity: 8, correctness: 9, completeness: 7 },
        confidence: 0.92
      },
      confidence: 0.92,
      human_override: null,
      status: "pending",
      created_at: "2026-04-01T10:00:00Z",
      updated_at: "2026-04-01T10:00:00Z"
    },
    {
      id: "eval-2",
      task_pack_id: "pack-1",
      task_id: "task-2",
      judge_model: "gpt-4o",
      evaluation_json: {
        preference: 2,
        reasoning: "Response B is more concise and correct.",
        dimensions: { clarity: 6, correctness: 8, completeness: 5 },
        confidence: 0.75
      },
      confidence: 0.75,
      human_override: null,
      status: "accepted",
      created_at: "2026-04-01T11:00:00Z",
      updated_at: "2026-04-02T09:00:00Z"
    }
  ],
  total: 2,
  limit: 50,
  offset: 0
};

const EMPTY_EVALUATIONS = { items: [], total: 0, limit: 50, offset: 0 };

async function mockRoutes(page: Page, auth: typeof MOCK_AUTH_ADMIN, evaluations = MOCK_EVALUATIONS) {
  await page.route("**/**/api/v1/auth/login", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(auth) });
  });

  await page.route("**/**/api/v1/sessions/*/workspace/**", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ revisions: [] }) });
  });

  await page.route("**/**/api/v1/sessions/*/workspace", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200, contentType: "application/json",
        body: JSON.stringify({ session_id: auth.session_id, annotator_id: auth.annotator.id, tasks: [], annotations: {}, task_times: {}, active_pack_file: null })
      });
      return;
    }
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ok: true, annotation_warnings: [] }) });
  });

  await page.route("**/**/api/v1/tasks/packs?*", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ packs: [MOCK_PACK], has_more: false, total_packs: 1, limit: 50 }) });
  });

  await page.route("**/**/api/v1/tasks/packs", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ packs: [MOCK_PACK], has_more: false, total_packs: 1, limit: 50 }) });
  });

  await page.route("**/**/api/v1/tasks/score-session", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ total_gold_tasks: 0, scored_tasks: 0, overall_accuracy: 0 }) });
  });

  await page.route("**/**/api/v1/judge/evaluations?*", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(evaluations) });
  });

  await page.route("**/**/api/v1/judge/evaluations", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(evaluations) });
      return;
    }
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({}) });
  });

  await page.route("**/**/api/v1/judge/evaluations/*/accept", async (route) => {
    const item = evaluations.items[0];
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ...item, status: "accepted" }) });
  });

  await page.route("**/**/api/v1/judge/evaluations/*/reject", async (route) => {
    const item = evaluations.items[0];
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ...item, status: "rejected" }) });
  });

  await page.route("**/**/api/v1/metrics/**", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ total_tasks: 0, completed_tasks: 0, skipped_tasks: 0, pending_tasks: 0, completion_rate: 0, avg_time_seconds: 0, median_time_seconds: 0, total_time_seconds: 0, dimension_averages: {}, tasks_by_type: {} }) });
  });

  await page.route("**/**/api/v1/inference/**", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ default: "gpt-4o", models: [] }) });
  });
}

async function loginAndGoToDashboard(page: Page, auth: typeof MOCK_AUTH_ADMIN) {
  await page.goto("/auth");
  await page.getByPlaceholder("Email").fill(auth.annotator.email);
  await page.getByPlaceholder(/Password/).fill("password123");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/dashboard/, { timeout: 15000 });
}

test.describe("Auto Reviews page", () => {
  test("admin sees Auto Reviews link in sidebar", async ({ page }) => {
    await mockRoutes(page, MOCK_AUTH_ADMIN);
    await loginAndGoToDashboard(page, MOCK_AUTH_ADMIN);
    await expect(page.getByRole("link", { name: "Auto Reviews" })).toBeVisible({ timeout: 10000 });
  });

  test("annotator does NOT see Auto Reviews link", async ({ page }) => {
    await mockRoutes(page, MOCK_AUTH_ANNOTATOR);
    await loginAndGoToDashboard(page, MOCK_AUTH_ANNOTATOR);
    await expect(page.getByRole("link", { name: "Auto Reviews" })).not.toBeVisible();
  });

  test("page renders title and stats cards", async ({ page }) => {
    await mockRoutes(page, MOCK_AUTH_ADMIN);
    await loginAndGoToDashboard(page, MOCK_AUTH_ADMIN);
    await page.goto("/auto-reviews");
    await expect(page.getByRole("heading", { name: "Auto Reviews" })).toBeVisible({ timeout: 15000 });
    await expect(page.getByText("Total (page)")).toBeVisible({ timeout: 10000 });
    await expect(page.getByText("Accepted", { exact: true }).first()).toBeVisible();
    await expect(page.getByText("Rejected", { exact: true }).first()).toBeVisible();
    await expect(page.getByText("Pending", { exact: true }).first()).toBeVisible();
    await expect(page.getByText("Avg Confidence")).toBeVisible();
  });

  test("shows filter controls", async ({ page }) => {
    await mockRoutes(page, MOCK_AUTH_ADMIN);
    await loginAndGoToDashboard(page, MOCK_AUTH_ADMIN);
    await page.goto("/auto-reviews");
    await expect(page.getByText("Task Pack")).toBeVisible({ timeout: 15000 });
    await expect(page.getByLabel("Status")).toBeVisible();
    await expect(page.getByRole("button", { name: "Refresh" })).toBeVisible();
  });

  test("shows evaluations in table with data", async ({ page }) => {
    await mockRoutes(page, MOCK_AUTH_ADMIN, MOCK_EVALUATIONS);
    await loginAndGoToDashboard(page, MOCK_AUTH_ADMIN);
    await page.goto("/auto-reviews");
    await expect(page.getByText("task-1")).toBeVisible({ timeout: 15000 });
    await expect(page.getByText("task-2")).toBeVisible();
    await expect(page.getByText("gpt-4o").first()).toBeVisible();
    await expect(page.getByText("Response A")).toBeVisible();
    await expect(page.getByText("Response B")).toBeVisible();
  });

  test("shows empty state when no evaluations", async ({ page }) => {
    await mockRoutes(page, MOCK_AUTH_ADMIN, EMPTY_EVALUATIONS);
    await loginAndGoToDashboard(page, MOCK_AUTH_ADMIN);
    await page.goto("/auto-reviews");
    await expect(page.getByText("No evaluations found")).toBeVisible({ timeout: 15000 });
  });

  test("expanding a row shows reasoning and dimensions", async ({ page }) => {
    await mockRoutes(page, MOCK_AUTH_ADMIN, MOCK_EVALUATIONS);
    await loginAndGoToDashboard(page, MOCK_AUTH_ADMIN);
    await page.goto("/auto-reviews");
    await expect(page.getByText("task-1")).toBeVisible({ timeout: 15000 });

    await page.getByText("task-1").click();

    await expect(page.getByRole("heading", { name: "Reasoning" })).toBeVisible({ timeout: 10000 });
    await expect(
      page.getByText("Response A provides a more thorough explanation")
    ).toBeVisible({ timeout: 10000 });
    await expect(page.getByRole("heading", { name: "Dimension Scores" })).toBeVisible();
    await expect(page.getByText("clarity").first()).toBeVisible();
    await expect(page.getByText("correctness").first()).toBeVisible();
    await expect(page.getByText("completeness").first()).toBeVisible();
  });

  test("accept button triggers API call", async ({ page }) => {
    let acceptCalled = false;
    await mockRoutes(page, MOCK_AUTH_ADMIN, MOCK_EVALUATIONS);
    await page.route("**/**/api/v1/judge/evaluations/*/accept", async (route) => {
      acceptCalled = true;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ ...MOCK_EVALUATIONS.items[0], status: "accepted" })
      });
    });
    await loginAndGoToDashboard(page, MOCK_AUTH_ADMIN);
    await page.goto("/auto-reviews");
    await expect(page.getByRole("button", { name: "Accept" }).first()).toBeVisible({ timeout: 15000 });
    await page.getByRole("button", { name: "Accept" }).first().click();
    await expect.poll(() => acceptCalled, { timeout: 10000 }).toBe(true);
  });

  test("reject button triggers API call", async ({ page }) => {
    let rejectCalled = false;
    await mockRoutes(page, MOCK_AUTH_ADMIN, MOCK_EVALUATIONS);
    await page.route("**/**/api/v1/judge/evaluations/*/reject", async (route) => {
      rejectCalled = true;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ ...MOCK_EVALUATIONS.items[0], status: "rejected" })
      });
    });
    await loginAndGoToDashboard(page, MOCK_AUTH_ADMIN);
    await page.goto("/auto-reviews");
    await expect(page.getByRole("button", { name: "Reject" }).first()).toBeVisible({ timeout: 15000 });
    await page.getByRole("button", { name: "Reject" }).first().click();
    await expect.poll(() => rejectCalled, { timeout: 10000 }).toBe(true);
  });

  test("override button opens modal", async ({ page }) => {
    await mockRoutes(page, MOCK_AUTH_ADMIN, MOCK_EVALUATIONS);
    await loginAndGoToDashboard(page, MOCK_AUTH_ADMIN);
    await page.goto("/auto-reviews");
    await expect(page.getByRole("button", { name: "Override" }).first()).toBeVisible({ timeout: 15000 });
    await page.getByRole("button", { name: "Override" }).first().click();
    await expect(page.getByRole("dialog")).toBeVisible({ timeout: 10000 });
    await expect(page.getByRole("heading", { name: "Override Evaluation" })).toBeVisible();
    await expect(page.getByLabel("Override Evaluation").getByText("Preference")).toBeVisible();
    await expect(page.getByPlaceholder("Explain why you are overriding")).toBeVisible();
  });

  test("annotator sees access restricted message", async ({ page }) => {
    await mockRoutes(page, MOCK_AUTH_ANNOTATOR);
    await loginAndGoToDashboard(page, MOCK_AUTH_ANNOTATOR);
    await page.goto("/auto-reviews");
    await expect(page.getByText("Access Restricted")).toBeVisible({ timeout: 15000 });
  });
});
