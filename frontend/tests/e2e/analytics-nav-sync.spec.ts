import { expect, test, type Page } from "@playwright/test";

/* ───── Mock data ───── */

const MOCK_AUTH = {
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
  task_count: 1,
  created_at: "2026-01-01T00:00:00Z"
};

const MOCK_TASK = {
  id: "task-1",
  type: "comparison" as const,
  title: "Fix buggy function",
  prompt: "Find the better fix.",
  responses: [
    { label: "A", text: "Use copy.deepcopy" },
    { label: "B", text: "Use list()" }
  ],
  dimensions: [{ name: "correctness", description: "Correctness", scale: 5 }]
};

const MOCK_METRICS = {
  total_tasks: 10,
  completed_tasks: 7,
  skipped_tasks: 2,
  pending_tasks: 1,
  completion_rate: 0.7,
  avg_time_seconds: 38,
  median_time_seconds: 32,
  total_time_seconds: 380,
  dimension_averages: { correctness: 3.80, clarity: 4.20, readability: 2.50 },
  tasks_by_type: { comparison: 5, rating: 3, ranking: 2 }
};

const MOCK_TIMELINE = {
  points: [
    { revision_number: 1, created_at: "2026-03-01T10:00:00Z", completed_count: 2 },
    { revision_number: 2, created_at: "2026-03-02T11:00:00Z", completed_count: 5 },
    { revision_number: 3, created_at: "2026-03-03T14:30:00Z", completed_count: 7 }
  ]
};

const WORKSPACE_WITH_TASKS = {
  session_id: MOCK_AUTH.session_id,
  annotator_id: MOCK_AUTH.annotator.id,
  tasks: [MOCK_TASK],
  annotations: { "task-1": { status: "active", dimensions: { correctness: 4 }, justification: "Good approach" } },
  task_times: { "task-1": 45 },
  active_pack_file: "debugging-exercises-python"
};

/* ───── Route mocking ───── */

async function mockAllRoutes(page: Page, opts: { useRichMetrics?: boolean; workspaceData?: typeof WORKSPACE_WITH_TASKS; putInterceptor?: (body: string) => void } = {}) {
  const useRichMetrics = opts.useRichMetrics ?? false;
  const workspaceData = opts.workspaceData ?? null;
  const putInterceptor = opts.putInterceptor;

  await page.route("**/**/api/v1/auth/login", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(MOCK_AUTH) });
  });

  await page.route("**/**/api/v1/sessions/*/workspace/**", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ revisions: [] }) });
  });

  await page.route("**/**/api/v1/sessions/*/workspace", async (route) => {
    if (route.request().method() === "GET") {
      const data = workspaceData ?? { session_id: MOCK_AUTH.session_id, annotator_id: MOCK_AUTH.annotator.id, tasks: [], annotations: {}, task_times: {}, active_pack_file: null };
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(data) });
      return;
    }
    if (route.request().method() === "PUT" && putInterceptor) {
      putInterceptor(route.request().postData() || "{}");
    }
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ok: true, annotation_warnings: [] }) });
  });

  await page.route("**/**/api/v1/tasks/packs", async (route) => {
    if (route.request().method() !== "GET") {
      await route.fulfill({ status: 201, contentType: "application/json", body: JSON.stringify(MOCK_PACK) });
      return;
    }
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ packs: [MOCK_PACK] }) });
  });

  await page.route("**/**/api/v1/tasks/packs/*", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ...MOCK_PACK, tasks_json: [MOCK_TASK] }) });
  });

  await page.route("**/**/api/v1/tasks/validate", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ok: true, strict_mode: false, total_tasks: 1, valid_tasks: 1, issues: [] }) });
  });

  await page.route("**/**/api/v1/tasks/score-session", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ total_gold_tasks: 0, scored_tasks: 0, overall_accuracy: 0 }) });
  });

  await page.route("**/**/api/v1/metrics/**", async (route) => {
    const url = route.request().url();
    if (url.includes("timeline")) {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(useRichMetrics ? MOCK_TIMELINE : { points: [] }) });
    } else {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(useRichMetrics ? MOCK_METRICS : { total_tasks: 0, completed_tasks: 0, skipped_tasks: 0, pending_tasks: 0, completion_rate: 0, avg_time_seconds: 0, median_time_seconds: 0, total_time_seconds: 0, dimension_averages: {}, tasks_by_type: {} }) });
    }
  });

  await page.route("**/**/api/v1/reviews/**", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) });
  });

  await page.route("**/**/api/v1/orgs/**", async (route) => {
    await route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ detail: "Not found" }) });
  });

  await page.route("**/**/api/v1/inference/**", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ default: "Qwen/Qwen2.5-7B-Instruct", models: [] }) });
  });
}

async function loginAndGoToDashboard(page: Page, opts: Parameters<typeof mockAllRoutes>[1] = {}) {
  await mockAllRoutes(page, opts);
  await page.goto("/auth");
  await page.getByPlaceholder("Email").fill(MOCK_AUTH.annotator.email);
  await page.getByPlaceholder("Password").fill("password123");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/dashboard/, { timeout: 15000 });
}

/* ═════════════════════════════════════════════
   ANALYTICS — DEEP
   ═════════════════════════════════════════════ */

test.describe("Analytics — metrics detail", () => {
  test("shows completion rate percentage", async ({ page }) => {
    await loginAndGoToDashboard(page, { useRichMetrics: true });
    await page.getByRole("link", { name: "View Analytics" }).click();
    await expect(page.getByText("70%")).toBeVisible({ timeout: 15000 });
  });

  test("shows completed, pending, and skipped counts", async ({ page }) => {
    await loginAndGoToDashboard(page, { useRichMetrics: true });
    await page.getByRole("link", { name: "View Analytics" }).click();
    await expect(page.getByText("7 done")).toBeVisible({ timeout: 15000 });
    await expect(page.getByText("1 pending")).toBeVisible();
    await expect(page.getByText("2 skipped")).toBeVisible();
  });

  test("shows total time card", async ({ page }) => {
    await loginAndGoToDashboard(page, { useRichMetrics: true });
    await page.getByRole("link", { name: "View Analytics" }).click();
    await expect(page.getByRole("heading", { name: "Total time" })).toBeVisible({ timeout: 15000 });
    await expect(page.getByText("Across 10 tasks")).toBeVisible();
  });

  test("shows avg and median time cards", async ({ page }) => {
    await loginAndGoToDashboard(page, { useRichMetrics: true });
    await page.getByRole("link", { name: "View Analytics" }).click();
    await expect(page.getByRole("heading", { name: "Avg time / task" })).toBeVisible({ timeout: 15000 });
    await expect(page.getByRole("heading", { name: "Median time / task" })).toBeVisible();
  });
});

test.describe("Analytics — dimension averages", () => {
  test("shows all dimension names with values", async ({ page }) => {
    await loginAndGoToDashboard(page, { useRichMetrics: true });
    await page.getByRole("link", { name: "View Analytics" }).click();
    await expect(page.getByRole("heading", { name: "Dimension averages" })).toBeVisible({ timeout: 15000 });
    await expect(page.getByText("clarity")).toBeVisible();
    await expect(page.getByText("4.20")).toBeVisible();
    await expect(page.getByText("correctness")).toBeVisible();
    await expect(page.getByText("3.80")).toBeVisible();
    await expect(page.getByText("readability")).toBeVisible();
    await expect(page.getByText("2.50")).toBeVisible();
  });
});

test.describe("Analytics — tasks by type", () => {
  test("shows type chips with counts", async ({ page }) => {
    await loginAndGoToDashboard(page, { useRichMetrics: true });
    await page.goto("/analytics");
    await expect(page.getByRole("heading", { name: "Tasks by type" })).toBeVisible({ timeout: 15000 });
    await expect(page.getByText("comparison")).toBeVisible();
    await expect(page.getByText("rating")).toBeVisible();
    await expect(page.getByText("ranking")).toBeVisible();
  });
});

test.describe("Analytics — timeline", () => {
  test("shows timeline table with revision rows", async ({ page }) => {
    await loginAndGoToDashboard(page, { useRichMetrics: true });
    await page.getByRole("link", { name: "View Analytics" }).click();
    await expect(page.getByRole("heading", { name: "Completion timeline" })).toBeVisible({ timeout: 15000 });
    await expect(page.getByRole("columnheader", { name: "Revision" })).toBeVisible();
    await expect(page.getByRole("columnheader", { name: "Timestamp" })).toBeVisible();
    await expect(page.getByRole("columnheader", { name: "Completed" })).toBeVisible();
    const rows = page.locator("tbody tr");
    await expect(rows).toHaveCount(3);
  });

  test("empty timeline shows message", async ({ page }) => {
    await loginAndGoToDashboard(page);
    await page.getByRole("link", { name: "View Analytics" }).click();
    await expect(page.getByText("No revision history yet")).toBeVisible({ timeout: 15000 });
  });
});

/* ═════════════════════════════════════════════
   NAVIGATION GUARDS
   ═════════════════════════════════════════════ */

test.describe("Navigation guards", () => {
  test("root path redirects to /auth", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveURL(/\/auth/, { timeout: 15000 });
  });

  test("unauthenticated /dashboard redirects to /auth", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page).toHaveURL(/\/auth/, { timeout: 15000 });
  });

  test("unauthenticated /analytics redirects to /auth", async ({ page }) => {
    await page.goto("/analytics");
    await expect(page).toHaveURL(/\/auth/, { timeout: 15000 });
  });

  test("unauthenticated /reviews redirects to /auth", async ({ page }) => {
    await page.goto("/reviews");
    await expect(page).toHaveURL(/\/auth/, { timeout: 15000 });
  });

  test("unauthenticated /settings redirects to /auth", async ({ page }) => {
    await page.goto("/settings");
    await expect(page).toHaveURL(/\/auth/, { timeout: 15000 });
  });

  test("unauthenticated /author redirects to /auth", async ({ page }) => {
    await page.goto("/author");
    await expect(page).toHaveURL(/\/auth/, { timeout: 15000 });
  });

  test("unauthenticated /team redirects to /auth", async ({ page }) => {
    await page.goto("/team");
    await expect(page).toHaveURL(/\/auth/, { timeout: 15000 });
  });

  test("/task/0 without tasks redirects to /dashboard", async ({ page }) => {
    await loginAndGoToDashboard(page);
    await page.goto("/task/0");
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 15000 });
  });
});

/* ═════════════════════════════════════════════
   WORKSPACE SYNC
   ═════════════════════════════════════════════ */

test.describe("Workspace sync", () => {
  test("restore from server button is visible on dashboard", async ({ page }) => {
    await loginAndGoToDashboard(page);
    await expect(page.getByRole("button", { name: "Restore from server" })).toBeVisible();
  });

  test("restore loads workspace snapshot from server", async ({ page }) => {
    await loginAndGoToDashboard(page, { workspaceData: WORKSPACE_WITH_TASKS });
    await page.getByRole("button", { name: "Restore from server" }).click();
    await expect(page.getByText("Restored")).toBeVisible({ timeout: 10000 });
  });

  test("loading pack shows Resume Annotation section on return", async ({ page }) => {
    await loginAndGoToDashboard(page);
    await page.getByRole("button", { name: "Load and Start" }).first().click();
    await expect(page).toHaveURL(/\/task\/0/, { timeout: 15000 });
    await page.getByRole("button", { name: "Back" }).click();
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 15000 });
    await expect(page.getByRole("heading", { name: "Resume Annotation" })).toBeVisible({ timeout: 10000 });
    await expect(page.getByRole("button", { name: "Open Task Workspace" })).toBeVisible();
  });

  test("Open Task Workspace button navigates to task page", async ({ page }) => {
    await loginAndGoToDashboard(page);
    await page.getByRole("button", { name: "Load and Start" }).first().click();
    await expect(page).toHaveURL(/\/task\/0/, { timeout: 15000 });
    await page.getByRole("button", { name: "Back" }).click();
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 15000 });
    await page.getByRole("button", { name: "Open Task Workspace" }).click();
    await expect(page).toHaveURL(/\/task\/0/, { timeout: 15000 });
  });
});
