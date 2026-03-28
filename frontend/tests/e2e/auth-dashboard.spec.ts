import { expect, test, type Page } from "@playwright/test";

test.setTimeout(60_000);

const MOCK_AUTH = {
  token: "fake-token",
  annotator: {
    id: "f5f5432e-57cd-4b22-84df-a35395f60529",
    name: "E2E User",
    email: "e2e@example.com",
    phone: null
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

async function mockAllRoutes(page: Page) {
  await page.route("**/**/api/v1/auth/login", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(MOCK_AUTH)
    });
  });

  await page.route("**/**/api/v1/sessions/*/workspace", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          session_id: MOCK_AUTH.session_id,
          annotator_id: MOCK_AUTH.annotator.id,
          tasks: [],
          annotations: {},
          task_times: {},
          active_pack_file: null
        })
      });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ ok: true, annotation_warnings: [] })
    });
  });

  await page.route("**/**/api/v1/tasks/packs", async (route) => {
    if (route.request().method() !== "GET") {
      await route.fulfill({ status: 201, contentType: "application/json", body: JSON.stringify(MOCK_PACK) });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ packs: [MOCK_PACK] })
    });
  });

  await page.route("**/**/api/v1/tasks/packs/*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ ...MOCK_PACK, tasks_json: [MOCK_TASK] })
    });
  });

  await page.route("**/**/api/v1/tasks/validate", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ ok: true, strict_mode: false, total_tasks: 1, valid_tasks: 1, issues: [] })
    });
  });

  await page.route("**/**/api/v1/tasks/score-session", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ total_gold_tasks: 0, scored_tasks: 0, overall_accuracy: 0 })
    });
  });

  await page.route("**/**/api/v1/metrics/**", async (route) => {
    const url = route.request().url();
    if (url.includes("timeline")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          points: [
            { revision_number: 1, created_at: "2026-03-01T10:00:00Z", completed_count: 1 },
            { revision_number: 2, created_at: "2026-03-01T11:00:00Z", completed_count: 3 }
          ]
        })
      });
    } else {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          total_tasks: 5,
          completed_tasks: 3,
          skipped_tasks: 1,
          pending_tasks: 1,
          completion_rate: 0.6,
          avg_time_seconds: 45,
          median_time_seconds: 40,
          total_time_seconds: 225,
          dimension_averages: { correctness: 3.5, clarity: 4.0 },
          tasks_by_type: { comparison: 3, rating: 2 }
        })
      });
    }
  });

  await page.route("**/**/api/v1/reviews/**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ assignments: [] })
    });
  });

  await page.route("**/**/api/v1/orgs/**", async (route) => {
    await route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ detail: "Not found" }) });
  });

  await page.route("**/**/api/v1/inference/**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ default: "Qwen/Qwen2.5-7B-Instruct", models: [] })
    });
  });
}

async function loginAndGoToDashboard(page: Page) {
  await mockAllRoutes(page);
  await page.goto("/auth");
  await page.getByPlaceholder("Email").fill("e2e@example.com");
  await page.getByPlaceholder("Password").fill("password123");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/dashboard/, { timeout: 15000 });
}

test("renders auth page", async ({ page }) => {
  await page.goto("/auth");
  await expect(page.getByRole("heading", { name: "RLHF Annotation Studio" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Login" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Register" })).toBeVisible();
});

test("login, load pack, and open task workflow", async ({ page }) => {
  await loginAndGoToDashboard(page);
  await expect(page.getByRole("heading", { name: "Task Library" })).toBeVisible();

  await page.getByRole("button", { name: "Load and Start" }).first().click();
  await expect(page).toHaveURL(/\/task\/0/, { timeout: 15000 });
  await expect(page.getByRole("heading", { level: 3, name: "Prompt" })).toBeVisible();
});

test("analytics page loads with metrics", async ({ page }) => {
  await loginAndGoToDashboard(page);
  await page.goto("/analytics");
  await expect(page.getByText("Completion Rate")).toBeVisible({ timeout: 15000 });
});

test("reviews page loads with tabs", async ({ page }) => {
  await loginAndGoToDashboard(page);
  await page.goto("/reviews");
  await expect(page.getByRole("heading", { name: "Review queue" })).toBeVisible({ timeout: 30000 });
});

test("settings page shows create org form", async ({ page }) => {
  await loginAndGoToDashboard(page);
  await page.goto("/settings");
  await expect(page.getByRole("heading", { name: "Settings" })).toBeVisible({ timeout: 30000 });
});

test("author page loads with pack form", async ({ page }) => {
  await loginAndGoToDashboard(page);
  await page.goto("/author");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible({ timeout: 15000 });
});
