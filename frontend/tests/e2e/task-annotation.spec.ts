import { expect, test, type Page } from "@playwright/test";

test.setTimeout(60_000);

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
  task_count: 3,
  created_at: "2026-01-01T00:00:00Z"
};

const COMPARISON_TASK = {
  id: "cmp-1",
  type: "comparison" as const,
  title: "Fix buggy function",
  prompt: "Which fix is better for the off-by-one error?",
  responses: [
    { label: "A", text: "Use range(1, n+1) to include the last element" },
    { label: "B", text: "Subtract 1 from the comparison in the while loop" }
  ],
  dimensions: [
    { name: "correctness", description: "Does it fix the bug?", scale: 5 },
    { name: "readability", description: "Is the code clear?", scale: 5 }
  ]
};

const RATING_TASK = {
  id: "rate-1",
  type: "rating" as const,
  title: "Rate explanation quality",
  prompt: "How well does this explain Python closures?",
  responses: [{ label: "Response", text: "A closure captures variables from its enclosing scope, allowing inner functions to access them after the outer function has returned." }],
  dimensions: [
    { name: "clarity", description: "Is the explanation clear?", scale: 5 },
    { name: "accuracy", description: "Is it technically correct?", scale: 5 }
  ]
};

const RANKING_TASK = {
  id: "rank-1",
  type: "ranking" as const,
  title: "Rank these solutions",
  prompt: "Order these approaches from best to worst.",
  responses: [
    { label: "A", text: "Use a hash map for O(1) lookups" },
    { label: "B", text: "Sort the array and binary search" },
    { label: "C", text: "Linear scan through the array" }
  ],
  dimensions: [{ name: "overall", description: "Overall quality", scale: 5 }]
};

async function mockAllRoutes(page: Page, tasks = [COMPARISON_TASK]) {
  await page.route("**/**/api/v1/auth/login", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(MOCK_AUTH) });
  });

  await page.route("**/**/api/v1/sessions/*/workspace/**", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ revisions: [] }) });
  });

  await page.route("**/**/api/v1/sessions/*/workspace", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ session_id: MOCK_AUTH.session_id, annotator_id: MOCK_AUTH.annotator.id, tasks: [], annotations: {}, task_times: {}, active_pack_file: null })
      });
      return;
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
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ...MOCK_PACK, tasks_json: tasks }) });
  });

  await page.route("**/**/api/v1/tasks/validate", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ok: true, strict_mode: false, total_tasks: tasks.length, valid_tasks: tasks.length, issues: [] }) });
  });

  await page.route("**/**/api/v1/tasks/score-session", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ total_gold_tasks: 0, scored_tasks: 0, overall_accuracy: 0 }) });
  });

  await page.route("**/**/api/v1/metrics/**", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ total_tasks: 0, completed_tasks: 0, skipped_tasks: 0, pending_tasks: 0, completion_rate: 0, avg_time_seconds: 0, median_time_seconds: 0, total_time_seconds: 0, dimension_averages: {}, tasks_by_type: {} }) });
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

async function loginLoadPackAndOpenTask(page: Page, tasks = [COMPARISON_TASK]) {
  await mockAllRoutes(page, tasks);
  await page.goto("/auth");
  await page.getByPlaceholder("Email").fill(MOCK_AUTH.annotator.email);
  await page.getByPlaceholder("Password").fill("password123");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/dashboard/, { timeout: 15000 });
  await page.getByRole("button", { name: "Load and Start" }).first().click();
  await expect(page).toHaveURL(/\/task\/0/, { timeout: 15000 });
}

async function advanceToPhase3(page: Page) {
  await page.getByRole("button", { name: /continue to streaming/i }).click();
  await expect(page.getByRole("button", { name: /review and annotate/i })).toBeVisible({ timeout: 15000 });
  await page.getByRole("button", { name: /review and annotate/i }).click();
  await expect(page.getByText("Review")).toBeVisible({ timeout: 10000 });
}

/* ═════════════════════════════════════════════
   TASK PAGE LAYOUT & PHASES
   ═════════════════════════════════════════════ */

test.describe("Task page layout", () => {
  test("shows task title with counter and phase indicator", async ({ page }) => {
    await loginLoadPackAndOpenTask(page);
    await expect(page.getByText("Fix buggy function (1/1)")).toBeVisible();
    await expect(page.getByText("Phase 1 of 3")).toBeVisible();
  });

  test("has Export and Back buttons in header", async ({ page }) => {
    await loginLoadPackAndOpenTask(page);
    await expect(page.getByRole("button", { name: "Export" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Back" })).toBeVisible();
  });

  test("Back button returns to dashboard", async ({ page }) => {
    await loginLoadPackAndOpenTask(page);
    await page.getByRole("button", { name: "Back" }).click();
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 15000 });
  });

  test("multi-task shows correct counter", async ({ page }) => {
    await loginLoadPackAndOpenTask(page, [COMPARISON_TASK, RATING_TASK, RANKING_TASK]);
    await expect(page.getByText("(1/3)")).toBeVisible();
  });
});

/* ═════════════════════════════════════════════
   EXPORT PANEL
   ═════════════════════════════════════════════ */

test.describe("Export panel", () => {
  test("toggle shows and hides export panel", async ({ page }) => {
    await loginLoadPackAndOpenTask(page);
    await page.getByRole("button", { name: "Export" }).click();
    await expect(page.getByRole("button", { name: "Copy Markdown" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Copy JSONL" })).toBeVisible();
    await page.getByRole("button", { name: "Hide Export" }).click();
    await expect(page.getByRole("button", { name: "Copy Markdown" })).not.toBeVisible();
  });
});

/* ═════════════════════════════════════════════
   COMPARISON ANNOTATION
   ═════════════════════════════════════════════ */

test.describe("Comparison task annotation", () => {
  test("phase 1 shows prompt text", async ({ page }) => {
    await loginLoadPackAndOpenTask(page);
    await expect(page.getByText("Which fix is better")).toBeVisible();
  });

  test("phase 3 shows preference buttons Choose A, Choose B, Tie", async ({ page }) => {
    await loginLoadPackAndOpenTask(page);
    await advanceToPhase3(page);
    await expect(page.getByRole("button", { name: "Choose A" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Choose B" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Tie" })).toBeVisible();
  });

  test("clicking Choose A highlights the button", async ({ page }) => {
    await loginLoadPackAndOpenTask(page);
    await advanceToPhase3(page);
    await page.getByRole("button", { name: "Choose A" }).click();
    const btn = page.getByRole("button", { name: "Choose A" });
    await expect(btn).toHaveClass(/btn-primary/);
  });

  test("clicking Tie highlights the Tie button", async ({ page }) => {
    await loginLoadPackAndOpenTask(page);
    await advanceToPhase3(page);
    await page.getByRole("button", { name: "Tie" }).click();
    await expect(page.getByRole("button", { name: "Tie" })).toHaveClass(/btn-primary/);
  });

  test("shows dimension score buttons for each dimension", async ({ page }) => {
    await loginLoadPackAndOpenTask(page);
    await advanceToPhase3(page);
    await expect(page.getByText("correctness")).toBeVisible();
    await expect(page.getByText("Does it fix the bug?")).toBeVisible();
    await expect(page.getByText("readability")).toBeVisible();
    await expect(page.getByText("Is the code clear?")).toBeVisible();
  });

  test("dimension score buttons go from 1 to scale", async ({ page }) => {
    await loginLoadPackAndOpenTask(page);
    await advanceToPhase3(page);
    const scoreButtons = page.locator("button").filter({ hasText: /^[1-5]$/ });
    const count = await scoreButtons.count();
    expect(count).toBeGreaterThanOrEqual(10);
  });

  test("shows justification textarea", async ({ page }) => {
    await loginLoadPackAndOpenTask(page);
    await advanceToPhase3(page);
    await expect(page.getByPlaceholder(/justification/i)).toBeVisible();
  });

  test("shows Previous, Skip, and Submit buttons", async ({ page }) => {
    await loginLoadPackAndOpenTask(page);
    await advanceToPhase3(page);
    await expect(page.getByRole("button", { name: "Previous" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Skip" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Submit and Next" })).toBeVisible();
  });

  test("Previous is disabled on first task", async ({ page }) => {
    await loginLoadPackAndOpenTask(page);
    await advanceToPhase3(page);
    await expect(page.getByRole("button", { name: "Previous" })).toBeDisabled();
  });
});

/* ═════════════════════════════════════════════
   RATING TASK
   ═════════════════════════════════════════════ */

test.describe("Rating task annotation", () => {
  test("shows single response with Response heading", async ({ page }) => {
    await loginLoadPackAndOpenTask(page, [RATING_TASK]);
    await advanceToPhase3(page);
    await expect(page.getByRole("heading", { name: "Response", level: 4 })).toBeVisible();
    await expect(page.getByText("A closure captures variables").first()).toBeVisible();
  });

  test("does NOT show Choose A/B or Tie buttons", async ({ page }) => {
    await loginLoadPackAndOpenTask(page, [RATING_TASK]);
    await advanceToPhase3(page);
    await expect(page.getByRole("button", { name: "Choose A" })).not.toBeVisible();
    await expect(page.getByRole("button", { name: "Tie" })).not.toBeVisible();
  });

  test("shows clarity and accuracy dimensions", async ({ page }) => {
    await loginLoadPackAndOpenTask(page, [RATING_TASK]);
    await advanceToPhase3(page);
    await expect(page.getByText("clarity")).toBeVisible();
    await expect(page.getByText("accuracy")).toBeVisible();
  });
});

/* ═════════════════════════════════════════════
   RANKING TASK
   ═════════════════════════════════════════════ */

test.describe("Ranking task annotation", () => {
  test("shows ordering instructions and Up/Down buttons", async ({ page }) => {
    await loginLoadPackAndOpenTask(page, [RANKING_TASK]);
    await advanceToPhase3(page);
    await expect(page.getByText("Order responses from best to worst")).toBeVisible();
    await expect(page.getByRole("button", { name: "Up" }).first()).toBeVisible();
    await expect(page.getByRole("button", { name: "Down" }).first()).toBeVisible();
  });

  test("shows all three responses with rank numbers", async ({ page }) => {
    await loginLoadPackAndOpenTask(page, [RANKING_TASK]);
    await advanceToPhase3(page);
    await expect(page.getByText("#1")).toBeVisible();
    await expect(page.getByText("#2")).toBeVisible();
    await expect(page.getByText("#3")).toBeVisible();
  });
});

/* ═════════════════════════════════════════════
   MULTI-TASK NAVIGATION
   ═════════════════════════════════════════════ */

test.describe("Multi-task navigation", () => {
  test("Skip advances to next task", async ({ page }) => {
    await loginLoadPackAndOpenTask(page, [COMPARISON_TASK, RATING_TASK]);
    await advanceToPhase3(page);
    await page.getByRole("button", { name: "Skip" }).click();
    await expect(page).toHaveURL(/\/task\/1/, { timeout: 10000 });
    await expect(page.getByText("(2/2)")).toBeVisible();
  });

  test("Skip on last task returns to dashboard", async ({ page }) => {
    await loginLoadPackAndOpenTask(page, [COMPARISON_TASK]);
    await advanceToPhase3(page);
    await page.getByRole("button", { name: "Skip" }).click();
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 15000 });
  });

  test("Previous navigates to prior task after skip", async ({ page }) => {
    await loginLoadPackAndOpenTask(page, [COMPARISON_TASK, RATING_TASK]);
    await advanceToPhase3(page);
    await page.getByRole("button", { name: "Skip" }).click();
    await expect(page).toHaveURL(/\/task\/1/, { timeout: 10000 });
    await advanceToPhase3(page);
    await page.getByRole("button", { name: "Previous" }).click();
    await expect(page).toHaveURL(/\/task\/0/, { timeout: 10000 });
  });
});
