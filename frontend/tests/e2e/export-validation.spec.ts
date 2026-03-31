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

const COMPARISON_TASK_2 = {
  ...COMPARISON_TASK,
  id: "cmp-2",
  title: "Second comparison task",
  prompt: "Pick the better follow-up fix.",
  responses: [
    { label: "A", text: "Second task response A" },
    { label: "B", text: "Second task response B" }
  ]
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
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ ok: true, strict_mode: false, total_tasks: tasks.length, valid_tasks: tasks.length, issues: [] })
    });
  });
  await page.route("**/**/api/v1/tasks/score-session", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ total_gold_tasks: 0, scored_tasks: 0, overall_accuracy: 0 }) });
  });
  await page.route("**/**/api/v1/metrics/**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        total_tasks: 0,
        completed_tasks: 0,
        skipped_tasks: 0,
        pending_tasks: 0,
        completion_rate: 0,
        avg_time_seconds: 0,
        median_time_seconds: 0,
        total_time_seconds: 0,
        dimension_averages: {},
        tasks_by_type: {}
      })
    });
  });
  await page.route("**/**/api/v1/reviews/**", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) });
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

/** Focus outside inputs so phase-3 keyboard shortcuts run. */
async function focusPhase3ForShortcuts(page: Page) {
  await page.getByRole("heading", { name: "Review" }).click();
}

/** Rate both comparison dimensions (two rows of 1–5) at the given score. */
async function rateBothDimensions(page: Page, score: number) {
  const label = String(score);
  const scoreBtns = page.getByRole("button", { name: label, exact: true });
  await scoreBtns.nth(0).click();
  await scoreBtns.nth(1).click();
}

/* ═════════════════════════════════════════════
   Submit validation
   ═════════════════════════════════════════════ */

test.describe("Submit validation", () => {
  test("Submit and Next requires preference selection", async ({ page }) => {
    await loginLoadPackAndOpenTask(page);
    await advanceToPhase3(page);
    await rateBothDimensions(page, 4);
    await page.getByPlaceholder(/justification/i).fill("Ten chars min justification text here.");
    await page.getByRole("button", { name: "Submit and Next" }).click();
    await expect(page.getByText(/select a preference/i)).toBeVisible({ timeout: 5000 });
    await expect(page).toHaveURL(/\/task\/0/);
  });

  test("Submit and Next requires all dimensions rated", async ({ page }) => {
    await loginLoadPackAndOpenTask(page);
    await advanceToPhase3(page);
    await page.getByRole("button", { name: "Choose A" }).click();
    await page.getByPlaceholder(/justification/i).fill("Ten chars min justification text here.");
    await page.getByRole("button", { name: "Submit and Next" }).click();
    await expect(page.getByText(/rate all dimensions/i)).toBeVisible({ timeout: 5000 });
    await expect(page).toHaveURL(/\/task\/0/);
  });

  test("Submit and Next requires justification >= 10 chars", async ({ page }) => {
    await loginLoadPackAndOpenTask(page);
    await advanceToPhase3(page);
    await page.getByRole("button", { name: "Choose A" }).click();
    await rateBothDimensions(page, 4);
    await page.getByPlaceholder(/justification/i).fill("short");
    await page.getByRole("button", { name: "Submit and Next" }).click();
    await expect(page.getByText(/at least 10 characters/i)).toBeVisible({ timeout: 5000 });
    await expect(page).toHaveURL(/\/task\/0/);
  });

  test("successful submit with all fields advances to next task or dashboard", async ({ page }) => {
    await loginLoadPackAndOpenTask(page, [COMPARISON_TASK, COMPARISON_TASK_2]);
    await advanceToPhase3(page);
    await page.getByRole("button", { name: "Choose A" }).click();
    await rateBothDimensions(page, 4);
    await page.getByPlaceholder(/justification/i).fill("Complete justification with enough length.");
    await page.getByRole("button", { name: "Submit and Next" }).click();
    await expect(page).toHaveURL(/\/task\/1/, { timeout: 15000 });
  });
});

/* ═════════════════════════════════════════════
   Export panel
   ═════════════════════════════════════════════ */

test.describe("Export panel", () => {
  test("export panel shows Copy Markdown and Copy JSONL buttons", async ({ page }) => {
    await loginLoadPackAndOpenTask(page);
    await page.getByRole("button", { name: "Export" }).click();
    await expect(page.getByRole("button", { name: "Copy Markdown" })).toBeVisible({ timeout: 10000 });
    await expect(page.getByRole("button", { name: "Copy JSONL" })).toBeVisible({ timeout: 10000 });
  });

  test("export with no completed tasks shows appropriate message", async ({ page }) => {
    const origin = process.env.E2E_BASE_URL || "http://localhost:3456";
    await page.context().grantPermissions(["clipboard-read", "clipboard-write"], { origin });
    await loginLoadPackAndOpenTask(page);
    await page.getByRole("button", { name: "Export" }).click();
    const exportSection = page.locator("section.card").filter({ has: page.getByRole("heading", { name: "Export" }) });
    await expect(exportSection).toBeVisible({ timeout: 10000 });
    await expect(exportSection.locator("pre")).toHaveCount(0);
    await page.getByRole("button", { name: "Copy Markdown" }).click();
    await expect(page.getByText("Markdown copied")).toBeVisible({ timeout: 5000 });
    const md = await page.evaluate(() => navigator.clipboard.readText());
    expect(md).not.toMatch(/Status:\s*done/i);
    expect(md).not.toMatch(/"status"\s*:\s*"done"/);
  });

  test("Copy Markdown button copies to clipboard", async ({ page }) => {
    const origin = process.env.E2E_BASE_URL || "http://localhost:3456";
    await page.context().grantPermissions(["clipboard-read", "clipboard-write"], { origin });
    await loginLoadPackAndOpenTask(page, [COMPARISON_TASK, COMPARISON_TASK_2]);
    await advanceToPhase3(page);
    await page.getByRole("button", { name: "Choose A" }).click();
    await rateBothDimensions(page, 4);
    await page.getByPlaceholder(/justification/i).fill("Complete justification with enough length.");
    await page.getByRole("button", { name: "Submit and Next" }).click();
    await expect(page).toHaveURL(/\/task\/1/, { timeout: 15000 });

    await page.getByRole("button", { name: "Export" }).click();
    await page.getByRole("button", { name: "Copy Markdown" }).click();
    await expect(page.getByText("Markdown copied")).toBeVisible({ timeout: 5000 });
    const md = await page.evaluate(() => navigator.clipboard.readText());
    expect(md).toContain("# RLHF Annotation Export");
    expect(md).toContain("Fix buggy function");
    expect(md).toMatch(/Status:\s*done/i);
    expect(md).toContain("cmp-1");
  });

  test("Copy JSONL button copies valid JSON lines", async ({ page }) => {
    const origin = process.env.E2E_BASE_URL || "http://localhost:3456";
    await page.context().grantPermissions(["clipboard-read", "clipboard-write"], { origin });
    await loginLoadPackAndOpenTask(page, [COMPARISON_TASK, COMPARISON_TASK_2]);
    await advanceToPhase3(page);
    await page.getByRole("button", { name: "Choose A" }).click();
    await rateBothDimensions(page, 4);
    await page.getByPlaceholder(/justification/i).fill("Complete justification with enough length.");
    await page.getByRole("button", { name: "Submit and Next" }).click();
    await expect(page).toHaveURL(/\/task\/1/, { timeout: 15000 });

    await page.getByRole("button", { name: "Export" }).click();
    await page.getByRole("button", { name: "Copy JSONL" }).click();
    await expect(page.getByText("JSONL copied")).toBeVisible({ timeout: 5000 });
    const raw = await page.evaluate(() => navigator.clipboard.readText());
    const lines = raw.trim().split("\n").filter(Boolean);
    expect(lines.length).toBe(2);
    for (const line of lines) {
      const row = JSON.parse(line) as { task_id: string; type: string; prompt: string; annotation: unknown };
      expect(row.task_id).toMatch(/^cmp-/);
      expect(row.type).toBe("comparison");
      expect(typeof row.prompt).toBe("string");
      expect(row).toHaveProperty("annotation");
    }
  });
});

/* ═════════════════════════════════════════════
   Keyboard shortcuts
   ═════════════════════════════════════════════ */

test.describe("Keyboard shortcuts", () => {
  test("pressing 1 selects Choose A preference", async ({ page }) => {
    await loginLoadPackAndOpenTask(page);
    await advanceToPhase3(page);
    await focusPhase3ForShortcuts(page);
    await page.keyboard.press("1");
    await expect(page.getByRole("button", { name: "Choose A" })).toHaveClass(/btn-primary/);
  });

  test("pressing 2 selects Choose B preference", async ({ page }) => {
    await loginLoadPackAndOpenTask(page);
    await advanceToPhase3(page);
    await focusPhase3ForShortcuts(page);
    await page.keyboard.press("2");
    await expect(page.getByRole("button", { name: "Choose B" })).toHaveClass(/btn-primary/);
  });

  test("pressing 3 selects Tie", async ({ page }) => {
    await loginLoadPackAndOpenTask(page);
    await advanceToPhase3(page);
    await focusPhase3ForShortcuts(page);
    await page.keyboard.press("3");
    await expect(page.getByRole("button", { name: "Tie" })).toHaveClass(/btn-primary/);
  });

  test("arrow right advances to next task", async ({ page }) => {
    await loginLoadPackAndOpenTask(page, [COMPARISON_TASK, COMPARISON_TASK_2]);
    await advanceToPhase3(page);
    await focusPhase3ForShortcuts(page);
    await page.keyboard.press("ArrowRight");
    await expect(page).toHaveURL(/\/task\/1/, { timeout: 15000 });
  });
});
