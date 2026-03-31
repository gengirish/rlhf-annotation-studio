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
  task_count: 2,
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
  responses: [{ label: "Response", text: "A closure captures variables from its enclosing scope." }],
  dimensions: [
    { name: "clarity", description: "Is the explanation clear?", scale: 5 },
    { name: "accuracy", description: "Is it technically correct?", scale: 5 }
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
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ total_gold_tasks: 0, scored_tasks: 0, overall_accuracy: 0 })
    });
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

/* ═════════════════════════════════════════════
   RESPONSIVE — MOBILE (375px)
   ═════════════════════════════════════════════ */

test.describe("Responsive — mobile viewport (375px)", () => {
  test("mobile: task page hides sidebar at 375px", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await loginLoadPackAndOpenTask(page);
    const sidebar = page.locator("[class*='sidebar']");
    const n = await sidebar.count();
    if (n > 0) {
      await expect(sidebar.first()).not.toBeVisible();
    } else {
      await expect(sidebar).toHaveCount(0);
    }
    await expect(page.getByRole("heading", { name: /Fix buggy function/ })).toBeVisible();
  });

  test("mobile: response cards stack vertically", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await loginLoadPackAndOpenTask(page);
    await advanceToPhase3(page);

    const cardA = page.locator("article.card").filter({ hasText: "Use range(1, n+1)" }).first();
    const cardB = page.locator("article.card").filter({ hasText: "Subtract 1 from the comparison" }).first();
    await expect(cardA).toBeVisible();
    await expect(cardB).toBeVisible();

    const layout = await page.evaluate(() => {
      const articles = [...document.querySelectorAll("article.card")];
      const hit = articles.find((a) => a.textContent?.includes("Use range(1, n+1)"));
      if (!hit) return { cols: "", stacked: false, rigidTwoCol: false };
      let el: HTMLElement | null = hit.parentElement;
      while (el && el !== document.body) {
        const gtc = el.style.gridTemplateColumns;
        if (gtc) {
          const rigidTwoCol = /\b1fr\s+1fr\b/.test(gtc) && !gtc.includes("auto-fit") && !gtc.includes("minmax");
          const boxA = hit.getBoundingClientRect();
          const siblings = [...el.querySelectorAll("article.card")].filter((c) => c !== hit);
          const other = siblings.find((c) => c.textContent?.includes("Subtract 1"));
          const stacked =
            !!other && other.getBoundingClientRect().top >= boxA.bottom - 4;
          return { cols: gtc, stacked, rigidTwoCol };
        }
        el = el.parentElement;
      }
      return { cols: "", stacked: false, rigidTwoCol: false };
    });

    expect(layout.rigidTwoCol).toBe(false);
    expect(layout.stacked).toBe(true);
    expect(layout.cols).toContain("auto-fit");

    const boxA = await cardA.boundingBox();
    const boxB = await cardB.boundingBox();
    expect(boxA && boxB).toBeTruthy();
    if (boxA && boxB) {
      expect(boxB.y).toBeGreaterThanOrEqual(boxA.y);
      expect(boxB.width).toBeGreaterThan(200);
    }
  });

  test("mobile: dashboard stats grid adapts", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await mockAllRoutes(page);
    await page.goto("/auth");
    await page.getByPlaceholder("Email").fill(MOCK_AUTH.annotator.email);
    await page.getByPlaceholder("Password").fill("password123");
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 15000 });

    const statsSection = page.locator("section").filter({ has: page.getByRole("heading", { name: "Tasks Loaded" }) }).first();
    await expect(statsSection).toBeVisible();
    await expect(page.getByRole("heading", { name: "Tasks Loaded" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Completed" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Current Pack" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Quality Score" })).toBeVisible();

    const boxes = await statsSection.locator("article.card").all();
    expect(boxes.length).toBeGreaterThanOrEqual(4);
    for (const card of boxes) {
      await expect(card).toBeVisible();
    }
  });
});

/* ═════════════════════════════════════════════
   RESPONSIVE — DESKTOP (1200px+)
   ═════════════════════════════════════════════ */

test.describe("Responsive — desktop viewport (1200px+)", () => {
  test("desktop: task page shows sidebar", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await loginLoadPackAndOpenTask(page, [COMPARISON_TASK, RATING_TASK]);

    const sidebar = page.locator("[class*='sidebar']");
    const n = await sidebar.count();
    if (n > 0) {
      await expect(sidebar.first()).toBeVisible();
    } else {
      await expect(page.getByRole("heading", { name: /Fix buggy function \(1\/2\)/ })).toBeVisible();
      await expect(page.getByRole("button", { name: "Back" })).toBeVisible();
    }
  });

  test("desktop: response cards show side by side", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await loginLoadPackAndOpenTask(page);
    await advanceToPhase3(page);

    const cardA = page.locator("article.card").filter({ hasText: "Use range(1, n+1)" }).first();
    const cardB = page.locator("article.card").filter({ hasText: "Subtract 1 from the comparison" }).first();
    await expect(cardA).toBeVisible();
    await expect(cardB).toBeVisible();

    const boxA = await cardA.boundingBox();
    const boxB = await cardB.boundingBox();
    expect(boxA && boxB).toBeTruthy();
    if (boxA && boxB) {
      expect(Math.abs(boxA.y - boxB.y)).toBeLessThan(32);
      expect(boxB.x).toBeGreaterThan(boxA.x);
    }
  });
});

/* ═════════════════════════════════════════════
   ACCESSIBILITY BASICS
   ═════════════════════════════════════════════ */

test.describe("Accessibility basics", () => {
  test("form inputs on auth page have associated labels or placeholders", async ({ page }) => {
    await page.goto("/auth");
    const email = page.getByPlaceholder("Email");
    const password = page.getByPlaceholder("Password");
    await expect(email).toBeVisible();
    await expect(password).toBeVisible();

    for (const loc of [email, password]) {
      const ph = await loc.getAttribute("placeholder");
      const aria = await loc.getAttribute("aria-label");
      const id = await loc.getAttribute("id");
      const hasLabel = id ? (await page.locator(`label[for="${id}"]`).count()) > 0 : false;
      expect(Boolean((ph && ph.trim()) || (aria && aria.trim()) || hasLabel)).toBe(true);
    }
  });

  test("form inputs on register page have labels", async ({ page }) => {
    await page.goto("/auth");
    await page.getByRole("button", { name: "Register" }).click();

    const nameInput = page.getByPlaceholder("Full name");
    const email = page.getByPlaceholder("Email");
    const password = page.getByPlaceholder("Password");
    await expect(nameInput).toBeVisible();
    await expect(email).toBeVisible();
    await expect(password).toBeVisible();

    for (const loc of [nameInput, email, password]) {
      const ph = await loc.getAttribute("placeholder");
      const aria = await loc.getAttribute("aria-label");
      const id = await loc.getAttribute("id");
      const hasLabel = id ? (await page.locator(`label[for="${id}"]`).count()) > 0 : false;
      expect(Boolean((ph && ph.trim()) || (aria && aria.trim()) || hasLabel)).toBe(true);
    }
  });

  test("task annotation controls are reachable", async ({ page }) => {
    await page.setViewportSize({ width: 900, height: 800 });
    await loginLoadPackAndOpenTask(page);
    await advanceToPhase3(page);

    await expect(page.getByRole("button", { name: "Choose A" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Choose B" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Tie" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Choose A" })).toBeEnabled();
    await expect(page.getByRole("button", { name: "Choose B" })).toBeEnabled();
    await expect(page.getByRole("button", { name: "Tie" })).toBeEnabled();

    await expect(page.getByText("correctness")).toBeVisible();
    await expect(page.getByText("readability")).toBeVisible();
    const scoreOne = page.getByRole("button", { name: "1", exact: true }).first();
    await expect(scoreOne).toBeVisible();
    await expect(scoreOne).toBeEnabled();

    const justification = page.getByPlaceholder(/justification/i);
    await expect(justification).toBeVisible();
    await expect(justification).toBeEnabled();

    const submit = page.getByRole("button", { name: "Submit and Next" });
    await expect(submit).toBeVisible();
    await expect(submit).toBeEnabled();
  });

  test("page has heading hierarchy", async ({ page }) => {
    await page.goto("/auth");
    await expect(page.getByRole("heading", { name: "RLHF Annotation Studio" })).toBeVisible();

    await mockAllRoutes(page);
    await page.goto("/auth");
    await page.getByPlaceholder("Email").fill(MOCK_AUTH.annotator.email);
    await page.getByPlaceholder("Password").fill("password123");
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 15000 });
    await expect(page.getByRole("heading", { name: /Welcome/ })).toBeVisible();

    await page.getByRole("button", { name: "Load and Start" }).first().click();
    await expect(page).toHaveURL(/\/task\/0/, { timeout: 15000 });
    await expect(page.getByRole("heading", { name: /Fix buggy function/ })).toBeVisible();
  });
});
