import { expect, test, type Page } from "@playwright/test";

/* ───── Mock data ───── */

const MOCK_AUTH = {
  token: "fake-token",
  annotator: {
    id: "f5f5432e-57cd-4b22-84df-a35395f60529",
    name: "E2E User",
    email: "e2e@example.com",
    phone: null,
    role: "admin",
    org_id: "org-001"
  },
  session_id: "4b94db28-59c6-4716-a890-1c7e58eca66d"
};

const MOCK_AUTH_NO_ORG = {
  ...MOCK_AUTH,
  annotator: { ...MOCK_AUTH.annotator, org_id: null }
};

const MOCK_ORG = {
  id: "org-001",
  name: "Test Organization",
  slug: "test-org",
  plan_tier: "free",
  max_seats: 5,
  max_packs: 3,
  used_seats: 2,
  used_packs: 1
};

const MOCK_MEMBERS = [
  { id: "f5f5432e-57cd-4b22-84df-a35395f60529", name: "E2E User", email: "e2e@example.com", role: "admin" },
  { id: "m2", name: "Team Member", email: "member@example.com", role: "annotator" }
];

const MOCK_PACK = {
  id: "pack-1",
  slug: "my-comparison-pack",
  name: "Comparison Pack",
  description: "A test comparison pack",
  language: "python",
  task_count: 1,
  created_at: "2026-01-01T00:00:00Z",
  tasks_json: [
    {
      id: "task-1",
      type: "comparison",
      title: "Test Task",
      prompt: "Which is better?",
      responses: [
        { label: "A", text: "Option A text" },
        { label: "B", text: "Option B text" }
      ],
      dimensions: [{ name: "quality", description: "Overall quality", scale: 5 }]
    }
  ]
};

/* ───── Route mocking ───── */

async function mockAllRoutes(page: Page, opts: { auth?: typeof MOCK_AUTH; hasOrg?: boolean; members?: typeof MOCK_MEMBERS } = {}) {
  const auth = opts.auth ?? MOCK_AUTH;
  const hasOrg = opts.hasOrg ?? true;
  const members = opts.members ?? MOCK_MEMBERS;

  await page.route("**/**/api/v1/auth/login", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(auth) });
  });

  await page.route("**/**/api/v1/sessions/*/workspace/**", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ revisions: [] }) });
  });

  await page.route("**/**/api/v1/sessions/*/workspace", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ session_id: auth.session_id, annotator_id: auth.annotator.id, tasks: [], annotations: {}, task_times: {}, active_pack_file: null }) });
      return;
    }
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ok: true, annotation_warnings: [] }) });
  });

  await page.route("**/**/api/v1/tasks/packs", async (route) => {
    if (route.request().method() !== "GET") {
      const body = JSON.parse(route.request().postData() || "{}");
      await route.fulfill({ status: 201, contentType: "application/json", body: JSON.stringify({ ...MOCK_PACK, ...body }) });
      return;
    }
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ packs: [MOCK_PACK] }) });
  });

  await page.route("**/**/api/v1/tasks/packs/*", async (route) => {
    if (route.request().method() === "DELETE") {
      await route.fulfill({ status: 204, body: "" });
      return;
    }
    if (route.request().method() === "PUT") {
      const body = JSON.parse(route.request().postData() || "{}");
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ...MOCK_PACK, ...body }) });
      return;
    }
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(MOCK_PACK) });
  });

  await page.route("**/**/api/v1/tasks/validate", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ok: true, strict_mode: false, total_tasks: 1, valid_tasks: 1, issues: [] }) });
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

  await page.route("**/**/api/v1/orgs", async (route) => {
    if (route.request().method() === "POST") {
      const body = JSON.parse(route.request().postData() || "{}");
      await route.fulfill({ status: 201, contentType: "application/json", body: JSON.stringify({ ...MOCK_ORG, ...body, id: "new-org-id" }) });
      return;
    }
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([MOCK_ORG]) });
  });

  await page.route("**/**/api/v1/orgs/**", async (route) => {
    const url = route.request().url();
    if (url.includes("/members") && route.request().method() === "POST") {
      await route.fulfill({ status: 201, contentType: "application/json", body: JSON.stringify({ id: "new-member", name: "New Member", email: "new@example.com", role: "annotator" }) });
    } else if (url.includes("/members")) {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(members) });
    } else if (!hasOrg) {
      await route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ detail: "Not found" }) });
    } else {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(MOCK_ORG) });
    }
  });

  await page.route("**/**/api/v1/inference/**", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ default: "Qwen/Qwen2.5-7B-Instruct", models: [] }) });
  });
}

async function loginAndGoToDashboard(page: Page, opts: Parameters<typeof mockAllRoutes>[1] & { setOrgId?: boolean } = {}) {
  const auth = opts.auth ?? MOCK_AUTH;
  await mockAllRoutes(page, opts);
  await page.goto("/auth");
  if (opts.setOrgId !== false && auth.annotator.org_id) {
    await page.evaluate((orgId) => localStorage.setItem("rlhf_active_org_id", orgId), auth.annotator.org_id);
  }
  await page.getByPlaceholder("Email").fill(auth.annotator.email);
  await page.getByPlaceholder(/Password/).fill("password123");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/dashboard/, { timeout: 15000 });
}

/* ═════════════════════════════════════════════
   SETTINGS — NO ORG
   ═════════════════════════════════════════════ */

test.describe("Settings — no organization", () => {
  test("shows Create Organization form when no org exists", async ({ page }) => {
    await loginAndGoToDashboard(page, { auth: MOCK_AUTH_NO_ORG, hasOrg: false });
    await page.goto("/settings");
    await expect(page.getByRole("heading", { name: "Settings" })).toBeVisible({ timeout: 30000 });
    await expect(page.getByRole("heading", { name: "Create Organization" })).toBeVisible({ timeout: 15000 });
    await expect(page.getByText("You do not have an organization yet")).toBeVisible();
  });

  test("create org form has name, slug, and submit", async ({ page }) => {
    await loginAndGoToDashboard(page, { auth: MOCK_AUTH_NO_ORG, hasOrg: false });
    await page.goto("/settings");
    await expect(page.getByRole("heading", { name: "Create Organization" })).toBeVisible({ timeout: 15000 });
    await expect(page.getByPlaceholder("Acme RLHF")).toBeVisible();
    await expect(page.getByPlaceholder("acme-rlhf")).toBeVisible();
    await expect(page.getByRole("button", { name: "Create Organization" })).toBeVisible();
  });

  test("slug auto-generates from name input", async ({ page }) => {
    await loginAndGoToDashboard(page, { auth: MOCK_AUTH_NO_ORG, hasOrg: false });
    await page.goto("/settings");
    await expect(page.getByPlaceholder("Acme RLHF")).toBeVisible({ timeout: 15000 });
    await page.getByPlaceholder("Acme RLHF").fill("My Test Org");
    await expect(page.getByPlaceholder("acme-rlhf")).toHaveValue("my-test-org");
  });

  test("creating org shows success toast", async ({ page }) => {
    await loginAndGoToDashboard(page, { auth: MOCK_AUTH_NO_ORG, hasOrg: false });
    await page.getByRole("link", { name: "Settings" }).click();
    await expect(page.getByPlaceholder("Acme RLHF")).toBeVisible({ timeout: 15000 });
    await page.getByPlaceholder("Acme RLHF").fill("New Org");
    await page.getByRole("button", { name: "Create Organization" }).click();
    await expect(page.getByText("Organization created")).toBeVisible({ timeout: 10000 });
  });
});

/* ═════════════════════════════════════════════
   SETTINGS — WITH ORG
   ═════════════════════════════════════════════ */

test.describe("Settings — existing organization", () => {
  test("shows org name, slug, and plan badge", async ({ page }) => {
    await loginAndGoToDashboard(page);
    await page.getByRole("link", { name: "Settings" }).click();
    await expect(page.getByRole("heading", { name: "Organization" })).toBeVisible({ timeout: 15000 });
    await expect(page.getByText("Test Organization")).toBeVisible();
    await expect(page.getByText("/test-org")).toBeVisible();
    await expect(page.getByText("free").first()).toBeVisible();
  });

  test("shows plan usage progress bars", async ({ page }) => {
    await loginAndGoToDashboard(page);
    await page.getByRole("link", { name: "Settings" }).click();
    await expect(page.getByRole("heading", { name: "Plan & usage" })).toBeVisible({ timeout: 15000 });
    await expect(page.getByText("Seats")).toBeVisible();
    await expect(page.getByText("Task packs")).toBeVisible();
  });

  test("shows team members list", async ({ page }) => {
    await loginAndGoToDashboard(page);
    await page.getByRole("link", { name: "Settings" }).click();
    await expect(page.getByRole("heading", { name: "Team members" })).toBeVisible({ timeout: 15000 });
    await expect(page.getByText("E2E User")).toBeVisible();
    await expect(page.getByText("Team Member", { exact: true })).toBeVisible();
    await expect(page.getByText("member@example.com")).toBeVisible();
  });

  test("shows invite member form with email input", async ({ page }) => {
    await loginAndGoToDashboard(page);
    await page.getByRole("link", { name: "Settings" }).click();
    await expect(page.getByPlaceholder("teammate@example.com")).toBeVisible({ timeout: 15000 });
    await expect(page.getByRole("button", { name: "Add member" })).toBeVisible();
  });

  test("inviting member shows success toast", async ({ page }) => {
    await loginAndGoToDashboard(page);
    await page.getByRole("link", { name: "Settings" }).click();
    await expect(page.getByPlaceholder("teammate@example.com")).toBeVisible({ timeout: 15000 });
    await page.getByPlaceholder("teammate@example.com").fill("new@example.com");
    await page.getByRole("button", { name: "Add member" }).click();
    await expect(page.getByText("Invitation sent")).toBeVisible({ timeout: 10000 });
  });

  test("has back to dashboard link", async ({ page }) => {
    await loginAndGoToDashboard(page);
    await page.getByRole("link", { name: "Settings" }).click();
    await expect(page.getByRole("link", { name: /Dashboard/i })).toBeVisible({ timeout: 15000 });
  });
});

/* ═════════════════════════════════════════════
   AUTHOR PAGE — LAYOUT
   ═════════════════════════════════════════════ */

test.describe("Author page — layout", () => {
  test("shows heading and back link", async ({ page }) => {
    await loginAndGoToDashboard(page);
    await page.getByRole("link", { name: "Author Tasks" }).click();
    await expect(page.getByRole("heading", { name: "Author task pack" })).toBeVisible({ timeout: 15000 });
    await expect(page.getByRole("link", { name: /Dashboard/i })).toBeVisible();
  });

  test("has load pack section with slug input and Load button", async ({ page }) => {
    await loginAndGoToDashboard(page);
    await page.getByRole("link", { name: "Author Tasks" }).click();
    await expect(page.getByRole("heading", { name: "Load existing pack" })).toBeVisible({ timeout: 15000 });
    await expect(page.getByPlaceholder("my-pack-slug")).toBeVisible();
    await expect(page.getByRole("button", { name: "Load" })).toBeVisible();
  });

  test("has pack metadata section with name, slug, description, language", async ({ page }) => {
    await loginAndGoToDashboard(page);
    await page.getByRole("link", { name: "Author Tasks" }).click();
    await expect(page.getByRole("heading", { name: "Pack metadata" })).toBeVisible({ timeout: 15000 });
    await expect(page.getByPlaceholder("My comparison pack")).toBeVisible();
    await expect(page.getByPlaceholder("my-pack", { exact: true })).toBeVisible();
    await expect(page.getByPlaceholder("What annotators will see")).toBeVisible();
  });

  test("has tasks section with default empty task", async ({ page }) => {
    await loginAndGoToDashboard(page);
    await page.getByRole("link", { name: "Author Tasks" }).click();
    await expect(page.getByRole("heading", { name: "Tasks" })).toBeVisible({ timeout: 15000 });
    await expect(page.getByText("Task 1")).toBeVisible();
    await expect(page.getByRole("button", { name: "Add task" })).toBeVisible();
  });

  test("has Validate and Save buttons", async ({ page }) => {
    await loginAndGoToDashboard(page);
    await page.getByRole("link", { name: "Author Tasks" }).click();
    await expect(page.getByRole("button", { name: "Validate" })).toBeVisible({ timeout: 15000 });
    await expect(page.getByRole("button", { name: "Save pack" })).toBeVisible();
  });
});

/* ═════════════════════════════════════════════
   AUTHOR PAGE — EDITING
   ═════════════════════════════════════════════ */

test.describe("Author page — editing", () => {
  test("name auto-generates slug", async ({ page }) => {
    await loginAndGoToDashboard(page);
    await page.getByRole("link", { name: "Author Tasks" }).click();
    await expect(page.getByPlaceholder("My comparison pack")).toBeVisible({ timeout: 15000 });
    await page.getByPlaceholder("My comparison pack").fill("Python Review Tasks");
    await expect(page.getByPlaceholder("my-pack", { exact: true })).toHaveValue("python-review-tasks");
  });

  test("Add task creates a second task card", async ({ page }) => {
    await loginAndGoToDashboard(page);
    await page.getByRole("link", { name: "Author Tasks" }).click();
    await expect(page.getByText("Task 1")).toBeVisible({ timeout: 15000 });
    await page.getByRole("button", { name: "Add task" }).click();
    await expect(page.getByText("Task 2")).toBeVisible();
  });

  test("Remove button removes a task card", async ({ page }) => {
    await loginAndGoToDashboard(page);
    await page.getByRole("link", { name: "Author Tasks" }).click();
    await expect(page.getByText("Task 1")).toBeVisible({ timeout: 15000 });
    await page.getByRole("button", { name: "Add task" }).click();
    await expect(page.getByText("Task 2")).toBeVisible();
    await page.getByRole("button", { name: "Remove" }).last().click();
    await expect(page.getByText("Task 2")).not.toBeVisible();
  });

  test("task card has type select with comparison, rating, ranking", async ({ page }) => {
    await loginAndGoToDashboard(page);
    await page.getByRole("link", { name: "Author Tasks" }).click();
    await expect(page.getByText("Task 1")).toBeVisible({ timeout: 15000 });
    const typeSelect = page.locator("select.input").filter({ has: page.locator("option[value='comparison']") }).first();
    await expect(typeSelect).toBeVisible({ timeout: 10000 });
    const options = await typeSelect.locator("option").allTextContents();
    expect(options).toContain("comparison");
    expect(options).toContain("rating");
    expect(options).toContain("ranking");
  });

  test("Add response and Add dimension buttons work", async ({ page }) => {
    await loginAndGoToDashboard(page);
    await page.getByRole("link", { name: "Author Tasks" }).click();
    await expect(page.getByText("Task 1")).toBeVisible({ timeout: 15000 });
    await expect(page.getByRole("button", { name: "Add response" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Add dimension" })).toBeVisible();
  });

  test("loading a pack shows success toast and populates fields", async ({ page }) => {
    await loginAndGoToDashboard(page);
    await page.getByRole("link", { name: "Author Tasks" }).click();
    await expect(page.getByPlaceholder("my-pack-slug")).toBeVisible({ timeout: 15000 });
    await page.getByPlaceholder("my-pack-slug").fill("my-comparison-pack");
    await page.getByRole("button", { name: "Load" }).click();
    await expect(page.getByText("Pack loaded for editing")).toBeVisible({ timeout: 10000 });
    await expect(page.getByRole("button", { name: "Delete pack" })).toBeVisible();
  });

  test("loading pack shows Save pack (update) button", async ({ page }) => {
    await loginAndGoToDashboard(page);
    await page.getByRole("link", { name: "Author Tasks" }).click();
    await expect(page.getByPlaceholder("my-pack-slug")).toBeVisible({ timeout: 15000 });
    await page.getByPlaceholder("my-pack-slug").fill("my-comparison-pack");
    await page.getByRole("button", { name: "Load" }).click();
    await expect(page.getByText("Pack loaded for editing")).toBeVisible({ timeout: 10000 });
    await expect(page.getByRole("button", { name: "Save pack (update)" })).toBeVisible();
  });
});

/* ═════════════════════════════════════════════
   SETTINGS INVITE FLOW
   ═════════════════════════════════════════════ */

test.describe("Settings invite flow", () => {
  test("invite member by email shows success feedback", async ({ page }) => {
    let invitePayload: { email?: string } | null = null;
    await mockAllRoutes(page);
    await page.route("**/**/api/v1/orgs/**", async (route) => {
      const url = route.request().url();
      if (url.includes("/members") && route.request().method() === "POST") {
        invitePayload = JSON.parse(route.request().postData() || "{}");
        await route.fulfill({
          status: 201,
          contentType: "application/json",
          body: JSON.stringify({
            id: "invited-member",
            name: "",
            email: invitePayload?.email ?? "",
            role: "annotator"
          })
        });
        return;
      }
      await route.fallback();
    });
    await page.goto("/auth");
    await page.evaluate(() => localStorage.setItem("rlhf_active_org_id", "org-001"));
    await page.getByPlaceholder("Email").fill(MOCK_AUTH.annotator.email);
    await page.getByPlaceholder(/Password/).fill("password123");
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 15000 });
    await page.goto("/settings");
    await expect(page.getByRole("heading", { name: "Team members" })).toBeVisible({ timeout: 15000 });
    await page.getByPlaceholder("teammate@example.com").fill("invitee@example.com");
    await page.getByRole("button", { name: "Add member" }).click();
    await expect(page.getByText("Invitation sent")).toBeVisible({ timeout: 10000 });
    expect(invitePayload?.email).toBe("invitee@example.com");
  });
});

/* ═════════════════════════════════════════════
   AUTHOR DELETE PACK
   ═════════════════════════════════════════════ */

test.describe("Author delete pack", () => {
  test("delete pack button triggers confirmation", async ({ page }) => {
    await loginAndGoToDashboard(page);
    await page.getByRole("link", { name: "Author Tasks" }).click();
    await expect(page.getByPlaceholder("my-pack-slug")).toBeVisible({ timeout: 15000 });
    await page.getByPlaceholder("my-pack-slug").fill("my-comparison-pack");
    await page.getByRole("button", { name: "Load" }).click();
    await expect(page.getByText("Pack loaded for editing")).toBeVisible({ timeout: 10000 });

    let dialogMessage = "";
    page.once("dialog", (dialog) => {
      dialogMessage = dialog.message();
      void dialog.dismiss();
    });
    await page.getByRole("button", { name: "Delete pack" }).click();
    expect(dialogMessage).toContain("Delete pack");
    expect(dialogMessage).toContain("my-comparison-pack");
    await expect(page.getByRole("button", { name: "Delete pack" })).toBeVisible();
  });
});
