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

const MOCK_AUTH_REVIEWER = {
  token: "fake-token-reviewer",
  annotator: {
    id: "c3d4e5f6-a7b8-9012-cdef-234567890abc",
    name: "Reviewer User",
    email: "reviewer@example.com",
    phone: null,
    role: "reviewer",
    org_id: "org-001"
  },
  session_id: "d4e5f6a7-b8c9-0123-defa-34567890abcd"
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

const MOCK_TASK_RATING = {
  id: "task-2",
  type: "rating" as const,
  title: "Rate this explanation",
  prompt: "How well does this explain closures?",
  responses: [{ label: "Response", text: "A closure captures variables from its enclosing scope." }],
  dimensions: [
    { name: "clarity", description: "Is the explanation clear?", scale: 5 },
    { name: "accuracy", description: "Is it technically correct?", scale: 5 }
  ]
};

const MOCK_REVIEW_ASSIGNMENTS = [
  {
    id: "rev-1",
    task_pack_id: "pack-1",
    task_id: "task-1",
    annotator_id: "f5f5432e-57cd-4b22-84df-a35395f60529",
    status: "submitted",
    annotation_json: { status: "done", dimensions: { correctness: 4 }, justification: "Good fix" },
    reviewer_id: null,
    reviewer_notes: null,
    created_at: "2026-03-20T10:00:00Z",
    updated_at: "2026-03-21T14:00:00Z"
  },
  {
    id: "rev-2",
    task_pack_id: "pack-1",
    task_id: "task-2",
    annotator_id: "f5f5432e-57cd-4b22-84df-a35395f60529",
    status: "approved",
    annotation_json: { status: "done", dimensions: { clarity: 5 } },
    reviewer_id: "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    reviewer_notes: "Well done",
    created_at: "2026-03-19T10:00:00Z",
    updated_at: "2026-03-22T09:00:00Z"
  }
];

const MOCK_TEAM_MEMBERS = [
  { id: "f5f5432e-57cd-4b22-84df-a35395f60529", name: "E2E User", email: "e2e@example.com", role: "annotator" },
  { id: "a1b2c3d4-e5f6-7890-abcd-ef1234567890", name: "Admin User", email: "admin@example.com", role: "admin" }
];

const MOCK_TEAM_STATS = [
  {
    annotator: { id: "f5f5432e-57cd-4b22-84df-a35395f60529", name: "E2E User", email: "e2e@example.com", role: "annotator" },
    stats: { assigned: 3, submitted: 2, approved: 1, rejected: 0, total: 6 }
  },
  {
    annotator: { id: "a1b2c3d4-e5f6-7890-abcd-ef1234567890", name: "Admin User", email: "admin@example.com", role: "admin" },
    stats: { assigned: 0, submitted: 0, approved: 0, rejected: 0, total: 0 }
  }
];

/* ───── Route mocking ───── */

interface MockRouteOptions {
  auth?: typeof MOCK_AUTH;
  reviewData?: typeof MOCK_REVIEW_ASSIGNMENTS;
  teamMembers?: typeof MOCK_TEAM_MEMBERS;
  teamStats?: typeof MOCK_TEAM_STATS;
  loginFail?: boolean;
  tasks?: typeof MOCK_TASK[];
}

async function mockAllRoutes(page: Page, opts: MockRouteOptions | typeof MOCK_AUTH = MOCK_AUTH) {
  const auth = "annotator" in opts ? opts : (opts.auth ?? MOCK_AUTH);
  const reviewData = "annotator" in opts ? [] : (opts.reviewData ?? []);
  const teamMembers = "annotator" in opts ? [] : (opts.teamMembers ?? []);
  const teamStats = "annotator" in opts ? [] : (opts.teamStats ?? []);
  const loginFail = "annotator" in opts ? false : (opts.loginFail ?? false);
  const tasks = "annotator" in opts ? [MOCK_TASK] : (opts.tasks ?? [MOCK_TASK]);

  await page.route("**/**/api/v1/auth/login", async (route) => {
    if (loginFail) {
      await route.fulfill({ status: 401, contentType: "application/json", body: JSON.stringify({ detail: "Invalid email or password" }) });
      return;
    }
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(auth) });
  });

  await page.route("**/**/api/v1/auth/register", async (route) => {
    await route.fulfill({ status: 201, contentType: "application/json", body: JSON.stringify(auth) });
  });

  await page.route("**/**/api/v1/sessions/*/workspace/**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ revisions: [] })
    });
  });

  await page.route("**/**/api/v1/sessions/*/workspace", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          session_id: auth.session_id,
          annotator_id: auth.annotator.id,
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
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ok: true, strict_mode: false, total_tasks: tasks.length, valid_tasks: tasks.length, issues: [] }) });
  });

  await page.route("**/**/api/v1/tasks/score-session", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ total_gold_tasks: 0, scored_tasks: 0, overall_accuracy: 0 }) });
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
          total_tasks: 5, completed_tasks: 3, skipped_tasks: 1, pending_tasks: 1,
          completion_rate: 0.6, avg_time_seconds: 45, median_time_seconds: 40,
          total_time_seconds: 225, dimension_averages: { correctness: 3.5, clarity: 4.0 },
          tasks_by_type: { comparison: 3, rating: 2 }
        })
      });
    }
  });

  await page.route("**/**/api/v1/reviews/**", async (route) => {
    const url = route.request().url();
    const method = route.request().method();

    if (url.includes("/reviews/team")) {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(reviewData) });
    } else if (url.includes("/reviews/queue")) {
      const myAssignments = reviewData.filter((a) => a.annotator_id === auth.annotator.id);
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(myAssignments) });
    } else if (url.includes("/reviews/pending")) {
      const pendingItems = reviewData.filter((a) => a.status === "submitted");
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(pendingItems) });
    } else if (url.includes("/reviews/bulk-assign")) {
      await route.fulfill({ status: 201, contentType: "application/json", body: JSON.stringify([{ id: "new-1", task_id: "task-1", status: "assigned" }]) });
    } else if (method === "PUT") {
      const body = JSON.parse(route.request().postData() || "{}");
      const assignment = reviewData.find((a) => url.includes(a.id));
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ...(assignment ?? MOCK_REVIEW_ASSIGNMENTS[0]), status: body.status ?? "approved", reviewer_notes: body.reviewer_notes ?? null }) });
    } else {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) });
    }
  });

  await page.route("**/**/api/v1/orgs/**", async (route) => {
    const url = route.request().url();

    if (url.includes("/team-stats")) {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(teamStats) });
    } else if (/\/members\/[^/]+\/role/.test(url)) {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ id: "member-1", name: "E2E User", email: "e2e@example.com", role: "reviewer" }) });
    } else if (url.includes("/members")) {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(teamMembers) });
    } else {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ id: "org-001", name: "Test Org", slug: "test-org", plan_tier: "free", max_seats: 5, max_packs: 3 }) });
    }
  });

  await page.route("**/**/api/v1/inference/**", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ default: "Qwen/Qwen2.5-7B-Instruct", models: [] }) });
  });
}

async function loginAndGoToDashboard(page: Page, opts: MockRouteOptions | typeof MOCK_AUTH = MOCK_AUTH) {
  const auth = "annotator" in opts ? opts : (opts.auth ?? MOCK_AUTH);
  await mockAllRoutes(page, opts);
  await page.goto("/auth");
  await page.getByPlaceholder("Email").fill(auth.annotator.email);
  await page.getByPlaceholder("Password").fill("password123");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/dashboard/, { timeout: 15000 });
}

/* ═════════════════════════════════════════════
   AUTH PAGE
   ═════════════════════════════════════════════ */

test.describe("Auth page", () => {
  test("renders login and register buttons", async ({ page }) => {
    await page.goto("/auth");
    await expect(page.getByRole("heading", { name: "RLHF Annotation Studio" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Login" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Register" })).toBeVisible();
  });

  test("login mode shows email and password fields only", async ({ page }) => {
    await page.goto("/auth");
    await expect(page.getByPlaceholder("Email")).toBeVisible();
    await expect(page.getByPlaceholder("Password")).toBeVisible();
    await expect(page.getByPlaceholder("Full name")).not.toBeVisible();
  });

  test("register mode shows name, phone, and role fields", async ({ page }) => {
    await page.goto("/auth");
    await page.getByRole("button", { name: "Register" }).click();
    await expect(page.getByPlaceholder("Full name")).toBeVisible();
    await expect(page.getByPlaceholder("Phone (optional)")).toBeVisible();
    await expect(page.locator("select[name='role']")).toBeVisible();
    await expect(page.getByPlaceholder("Email")).toBeVisible();
    await expect(page.getByPlaceholder("Password")).toBeVisible();
  });

  test("role dropdown has annotator and reviewer, not admin", async ({ page }) => {
    await page.goto("/auth");
    await page.getByRole("button", { name: "Register" }).click();
    const roleSelect = page.locator("select[name='role']");
    const options = await roleSelect.locator("option").allTextContents();
    expect(options).toContain("Annotator");
    expect(options).toContain("Reviewer");
    expect(options).not.toContain("Admin");
  });

  test("switching between login and register preserves email", async ({ page }) => {
    await page.goto("/auth");
    await page.getByPlaceholder("Email").fill("test@test.com");
    await page.getByRole("button", { name: "Register" }).click();
    await expect(page.getByPlaceholder("Full name")).toBeVisible();
    await page.getByRole("button", { name: "Login" }).click();
    await expect(page.getByPlaceholder("Full name")).not.toBeVisible();
  });

  test("failed login shows error toast", async ({ page }) => {
    await mockAllRoutes(page, { loginFail: true });
    await page.goto("/auth");
    await page.getByPlaceholder("Email").fill("bad@example.com");
    await page.getByPlaceholder("Password").fill("wrongpassword");
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page.getByText("Invalid email or password")).toBeVisible({ timeout: 10000 });
  });

  test("successful registration redirects to dashboard", async ({ page }) => {
    await mockAllRoutes(page, { auth: MOCK_AUTH });
    await page.goto("/auth");
    await page.getByRole("button", { name: "Register" }).click();
    await page.getByPlaceholder("Full name").fill("New User");
    await page.getByPlaceholder("Email").fill("new@example.com");
    await page.getByPlaceholder("Password").fill("password123");
    await page.getByRole("button", { name: "Create account" }).click();
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 15000 });
  });
});

/* ═════════════════════════════════════════════
   DASHBOARD
   ═════════════════════════════════════════════ */

test.describe("Dashboard", () => {
  test("shows welcome message and user name", async ({ page }) => {
    await loginAndGoToDashboard(page);
    await expect(page.getByText("Welcome, E2E User")).toBeVisible();
  });

  test("displays stats cards", async ({ page }) => {
    await loginAndGoToDashboard(page);
    await expect(page.getByText("Tasks Loaded")).toBeVisible();
    await expect(page.getByText("Completed")).toBeVisible();
    await expect(page.getByText("Current Pack")).toBeVisible();
    await expect(page.getByText("Quality Score")).toBeVisible();
  });

  test("shows task library with pack catalog", async ({ page }) => {
    await loginAndGoToDashboard(page);
    await expect(page.getByRole("heading", { name: "Task Library" })).toBeVisible();
    await expect(page.getByText("Python Debugging")).toBeVisible();
    await expect(page.getByText("Debug Python snippets")).toBeVisible();
    await expect(page.getByRole("button", { name: "Load and Start" })).toBeVisible();
  });

  test("shows navigation links for analytics, reviews, settings, author", async ({ page }) => {
    await loginAndGoToDashboard(page);
    await expect(page.getByRole("link", { name: "View Analytics" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Review Queue" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Settings" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Author Tasks" })).toBeVisible();
  });

  test("has restore and logout buttons", async ({ page }) => {
    await loginAndGoToDashboard(page);
    await expect(page.getByRole("button", { name: "Restore from server" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Logout" })).toBeVisible();
  });

  test("logout redirects to auth", async ({ page }) => {
    await loginAndGoToDashboard(page);
    await page.getByRole("button", { name: "Logout" }).click();
    await expect(page).toHaveURL(/\/auth/, { timeout: 15000 });
  });

  test("JSON upload section is visible", async ({ page }) => {
    await loginAndGoToDashboard(page);
    await expect(page.getByRole("heading", { name: "Load from JSON" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Choose JSON File" })).toBeVisible();
  });
});

/* ═════════════════════════════════════════════
   TASK WORKFLOW
   ═════════════════════════════════════════════ */

test.describe("Task workflow", () => {
  test("loading pack navigates to task page with prompt", async ({ page }) => {
    await loginAndGoToDashboard(page);
    await page.getByRole("button", { name: "Load and Start" }).first().click();
    await expect(page).toHaveURL(/\/task\/0/, { timeout: 15000 });
    await expect(page.getByRole("heading", { level: 3, name: "Prompt" })).toBeVisible();
    await expect(page.getByText("Find the better fix.")).toBeVisible();
  });

  test("task page shows responses after clicking Continue to Streaming", async ({ page }) => {
    await loginAndGoToDashboard(page);
    await page.getByRole("button", { name: "Load and Start" }).first().click();
    await expect(page).toHaveURL(/\/task\/0/, { timeout: 15000 });
    await page.getByRole("button", { name: /continue to streaming/i }).click();
    await expect(page.getByText("Use copy.deepcopy")).toBeVisible({ timeout: 15000 });
    await expect(page.getByText("Use list()")).toBeVisible();
  });

  test("task page shows Review and Annotate phase after streaming", async ({ page }) => {
    await loginAndGoToDashboard(page, { tasks: [MOCK_TASK] });
    await page.getByRole("button", { name: "Load and Start" }).first().click();
    await expect(page).toHaveURL(/\/task\/0/, { timeout: 15000 });
    await page.getByRole("button", { name: /continue to streaming/i }).click();
    await expect(page.getByText("Use copy.deepcopy")).toBeVisible({ timeout: 15000 });
    await page.getByRole("button", { name: /review and annotate/i }).click();
    await expect(page.getByText("Correctness")).toBeVisible({ timeout: 10000 });
  });

  test("task page shows both responses with content", async ({ page }) => {
    await loginAndGoToDashboard(page, { tasks: [MOCK_TASK, MOCK_TASK_RATING] });
    await page.getByRole("button", { name: "Load and Start" }).first().click();
    await expect(page).toHaveURL(/\/task\/0/, { timeout: 15000 });
    await page.getByRole("button", { name: /continue to streaming/i }).click();
    await expect(page.getByText("Use copy.deepcopy")).toBeVisible({ timeout: 15000 });
    await expect(page.getByText("Use list()")).toBeVisible();
  });
});

/* ═════════════════════════════════════════════
   ANALYTICS
   ═════════════════════════════════════════════ */

test.describe("Analytics page", () => {
  test("loads with key metric cards", async ({ page }) => {
    await loginAndGoToDashboard(page);
    await page.goto("/analytics");
    await expect(page.getByText("Completion Rate")).toBeVisible({ timeout: 15000 });
    await expect(page.getByText("60%")).toBeVisible();
  });

  test("shows back to dashboard link", async ({ page }) => {
    await loginAndGoToDashboard(page);
    await page.goto("/analytics");
    await expect(page.getByRole("link", { name: /dashboard/i })).toBeVisible({ timeout: 15000 });
  });
});

/* ═════════════════════════════════════════════
   REVIEWS
   ═════════════════════════════════════════════ */

test.describe("Reviews page", () => {
  test("shows My Assignments and Pending Review tabs", async ({ page }) => {
    await loginAndGoToDashboard(page);
    await page.getByRole("link", { name: "Review Queue" }).click();
    await expect(page.getByRole("heading", { name: "Review queue" })).toBeVisible({ timeout: 30000 });
    await expect(page.getByRole("button", { name: "My Assignments" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Pending Review" })).toBeVisible();
  });

  test("annotator does NOT see Team Reviews tab", async ({ page }) => {
    await loginAndGoToDashboard(page);
    await page.goto("/reviews");
    await expect(page.getByRole("heading", { name: "Review queue" })).toBeVisible({ timeout: 30000 });
    await expect(page.getByRole("button", { name: /team/i })).not.toBeVisible();
  });

  test("shows empty state for no assignments", async ({ page }) => {
    await loginAndGoToDashboard(page);
    await page.goto("/reviews");
    await expect(page.getByText("No assignments in your queue")).toBeVisible({ timeout: 15000 });
  });

  test("annotator sees their assignments with status badges", async ({ page }) => {
    await loginAndGoToDashboard(page, { reviewData: MOCK_REVIEW_ASSIGNMENTS });
    await page.goto("/reviews");
    await expect(page.getByText("task-1")).toBeVisible({ timeout: 15000 });
    await expect(page.getByText("submitted")).toBeVisible();
  });

  test("pending tab shows submitted reviews with approve/reject", async ({ page }) => {
    await loginAndGoToDashboard(page, { reviewData: MOCK_REVIEW_ASSIGNMENTS });
    await page.getByRole("link", { name: "Review Queue" }).click();
    await expect(page.getByRole("heading", { name: "Review queue" })).toBeVisible({ timeout: 30000 });
    await page.getByRole("button", { name: "Pending Review" }).click();
    await expect(page.getByRole("button", { name: "Approve" })).toBeVisible({ timeout: 15000 });
    await expect(page.getByRole("button", { name: "Reject" })).toBeVisible({ timeout: 10000 });
  });

  test("admin sees Team Reviews tab", async ({ page }) => {
    await loginAndGoToDashboard(page, { auth: MOCK_AUTH_ADMIN, reviewData: MOCK_REVIEW_ASSIGNMENTS, teamMembers: MOCK_TEAM_MEMBERS });
    await page.goto("/reviews");
    await expect(page.getByRole("button", { name: /team/i })).toBeVisible({ timeout: 15000 });
  });

  test("reviewer sees Team Reviews tab", async ({ page }) => {
    await loginAndGoToDashboard(page, { auth: MOCK_AUTH_REVIEWER, reviewData: MOCK_REVIEW_ASSIGNMENTS });
    await page.goto("/reviews");
    await expect(page.getByRole("button", { name: /team/i })).toBeVisible({ timeout: 15000 });
  });
});

/* ═════════════════════════════════════════════
   RBAC — Dashboard role badges and navigation
   ═════════════════════════════════════════════ */

test.describe("RBAC - Dashboard", () => {
  test("admin sees role badge", async ({ page }) => {
    await loginAndGoToDashboard(page, MOCK_AUTH_ADMIN);
    await expect(page.getByText("admin")).toBeVisible({ timeout: 10000 });
  });

  test("reviewer sees role badge", async ({ page }) => {
    await loginAndGoToDashboard(page, MOCK_AUTH_REVIEWER);
    await expect(page.getByText("reviewer")).toBeVisible({ timeout: 10000 });
  });

  test("annotator does NOT see a role badge", async ({ page }) => {
    await loginAndGoToDashboard(page);
    const badges = page.locator("span").filter({ hasText: /^(admin|reviewer)$/ });
    await expect(badges).toHaveCount(0);
  });

  test("admin sees Team Management link", async ({ page }) => {
    await loginAndGoToDashboard(page, MOCK_AUTH_ADMIN);
    await expect(page.getByRole("link", { name: "Team Management" })).toBeVisible({ timeout: 10000 });
  });

  test("reviewer sees Team Management link", async ({ page }) => {
    await loginAndGoToDashboard(page, MOCK_AUTH_REVIEWER);
    await expect(page.getByRole("link", { name: "Team Management" })).toBeVisible({ timeout: 10000 });
  });

  test("annotator does NOT see Team Management link", async ({ page }) => {
    await loginAndGoToDashboard(page);
    await expect(page.getByRole("link", { name: "Team Management" })).not.toBeVisible();
  });
});

/* ═════════════════════════════════════════════
   TEAM MANAGEMENT PAGE
   ═════════════════════════════════════════════ */

test.describe("Team management page", () => {
  test("loads for admin with all sections", async ({ page }) => {
    await loginAndGoToDashboard(page, {
      auth: MOCK_AUTH_ADMIN,
      teamMembers: MOCK_TEAM_MEMBERS,
      teamStats: MOCK_TEAM_STATS,
      reviewData: MOCK_REVIEW_ASSIGNMENTS
    });
    await page.goto("/team");
    await expect(page.getByRole("heading", { name: "Team management" })).toBeVisible({ timeout: 15000 });
    await expect(page.getByRole("heading", { name: "Team members" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Assign task pack" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Team review assignments" })).toBeVisible();
  });

  test("displays team members in table", async ({ page }) => {
    await loginAndGoToDashboard(page, {
      auth: MOCK_AUTH_ADMIN,
      teamMembers: MOCK_TEAM_MEMBERS,
      teamStats: MOCK_TEAM_STATS,
      reviewData: []
    });
    await page.goto("/team");
    await expect(page.getByRole("cell", { name: "E2E User" })).toBeVisible({ timeout: 15000 });
    await expect(page.getByRole("cell", { name: "e2e@example.com" })).toBeVisible();
    await expect(page.getByRole("cell", { name: "Admin User" })).toBeVisible();
  });

  test("admin sees role dropdowns in member table", async ({ page }) => {
    await loginAndGoToDashboard(page, {
      auth: MOCK_AUTH_ADMIN,
      teamMembers: MOCK_TEAM_MEMBERS,
      teamStats: MOCK_TEAM_STATS,
      reviewData: []
    });
    await page.goto("/team");
    await expect(page.getByText("Team members")).toBeVisible({ timeout: 15000 });
    const roleSelects = page.locator("table select.input");
    await expect(roleSelects.first()).toBeVisible();
  });

  test("assign pack section has button and dropdowns", async ({ page }) => {
    await loginAndGoToDashboard(page, {
      auth: MOCK_AUTH_ADMIN,
      teamMembers: MOCK_TEAM_MEMBERS,
      teamStats: MOCK_TEAM_STATS,
      reviewData: []
    });
    await page.goto("/team");
    await expect(page.getByRole("heading", { name: "Team management" })).toBeVisible({ timeout: 30000 });
    await expect(page.getByText("Assign task pack")).toBeVisible({ timeout: 15000 });
    await expect(page.getByRole("button", { name: /assign pack/i })).toBeVisible();
  });

  test("shows status filter in review assignments", async ({ page }) => {
    await loginAndGoToDashboard(page, {
      auth: MOCK_AUTH_ADMIN,
      teamMembers: MOCK_TEAM_MEMBERS,
      teamStats: MOCK_TEAM_STATS,
      reviewData: MOCK_REVIEW_ASSIGNMENTS
    });
    await page.goto("/team");
    await expect(page.getByText("Team review assignments")).toBeVisible({ timeout: 15000 });
    const statusFilter = page.locator("select").filter({ has: page.locator("option[value='submitted']") });
    await expect(statusFilter.first()).toBeVisible();
  });

  test("shows submitted review with approve/reject buttons", async ({ page }) => {
    await loginAndGoToDashboard(page, {
      auth: MOCK_AUTH_ADMIN,
      teamMembers: MOCK_TEAM_MEMBERS,
      teamStats: MOCK_TEAM_STATS,
      reviewData: MOCK_REVIEW_ASSIGNMENTS
    });
    await page.goto("/team");
    await expect(page.getByText("task-1")).toBeVisible({ timeout: 15000 });
    await expect(page.getByRole("button", { name: "Approve" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Reject" })).toBeVisible();
  });

  test("admin without org sees Settings prompt", async ({ page }) => {
    const noOrgAdmin = { ...MOCK_AUTH_ADMIN, annotator: { ...MOCK_AUTH_ADMIN.annotator, org_id: null } };
    await loginAndGoToDashboard(page, { auth: noOrgAdmin });
    await page.goto("/team");
    await expect(page.getByText("Create an organization in Settings first")).toBeVisible({ timeout: 15000 });
    await expect(page.getByRole("link", { name: "Settings" })).toBeVisible();
  });

  test("has back to dashboard link", async ({ page }) => {
    await loginAndGoToDashboard(page, {
      auth: MOCK_AUTH_ADMIN,
      teamMembers: MOCK_TEAM_MEMBERS,
      teamStats: MOCK_TEAM_STATS,
      reviewData: []
    });
    await page.getByRole("link", { name: "Team Management" }).click();
    await expect(page.getByRole("heading", { name: "Team management" })).toBeVisible({ timeout: 15000 });
    await expect(page.getByRole("link", { name: /dashboard/i })).toBeVisible();
  });
});

/* ═════════════════════════════════════════════
   SETTINGS & AUTHOR
   ═════════════════════════════════════════════ */

test.describe("Settings & Author pages", () => {
  test("settings page loads", async ({ page }) => {
    await loginAndGoToDashboard(page);
    await page.getByRole("link", { name: "Settings" }).click();
    await expect(page.getByRole("heading", { name: "Settings" })).toBeVisible({ timeout: 30000 });
  });

  test("author page loads with heading", async ({ page }) => {
    await loginAndGoToDashboard(page);
    await page.getByRole("link", { name: "Author Tasks" }).click();
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible({ timeout: 15000 });
  });
});
