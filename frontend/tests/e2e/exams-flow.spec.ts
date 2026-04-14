import { expect, test, type Page } from "@playwright/test";

const AUTH_ANNOTATOR = {
  token: "fake-token-annotator",
  annotator: {
    id: "u-annotator-1",
    name: "Exam Candidate",
    email: "candidate@example.com",
    phone: null,
    role: "annotator",
    org_id: "org-001"
  },
  session_id: "session-annotator-1"
};

const AUTH_REVIEWER = {
  token: "fake-token-reviewer",
  annotator: {
    id: "u-reviewer-1",
    name: "Exam Reviewer",
    email: "reviewer@example.com",
    phone: null,
    role: "reviewer",
    org_id: "org-001"
  },
  session_id: "session-reviewer-1"
};

const EXAM = {
  id: "exam-1",
  title: "Final Practical Exam",
  description: "Timed practical certification",
  task_pack_id: "pack-uuid-1",
  duration_minutes: 30,
  pass_threshold: 0.7,
  max_attempts: 2,
  is_published: true,
  created_by: "u-reviewer-1",
  created_at: "2026-04-11T00:00:00Z",
  updated_at: "2026-04-11T00:00:00Z"
};

const TASK_PACK_SUMMARY = {
  id: "pack-uuid-1",
  slug: "exam-pack-1",
  name: "Exam Pack 1",
  description: "Pack used by exam",
  language: "python",
  task_count: 1,
  created_at: "2026-04-11T00:00:00Z"
};

const TASK_PACK_DETAIL = {
  ...TASK_PACK_SUMMARY,
  tasks_json: [
    {
      id: "q1",
      type: "comparison",
      title: "Pick the safer patch",
      prompt: "Which patch is safer for production deployment?",
      responses: [
        { label: "A", text: "Patch A response text" },
        { label: "B", text: "Patch B response text" }
      ],
      dimensions: [{ name: "safety", description: "Safety and robustness", scale: 5 }]
    }
  ]
};

const ACTIVE_ATTEMPT = {
  id: "attempt-1",
  exam_id: "exam-1",
  annotator_id: "u-annotator-1",
  started_at: "2026-04-11T00:00:00Z",
  expires_at: "2099-04-11T00:30:00Z",
  submitted_at: null,
  status: "active",
  score: null,
  passed: null,
  answers_json: {},
  task_times_json: {},
  integrity_score: 1.0,
  review_notes: null,
  released_at: null,
  released_by: null
};

const REVIEW_QUEUE = [
  {
    id: "attempt-2",
    exam_id: "exam-1",
    exam_title: "Final Practical Exam",
    annotator_id: "u-annotator-2",
    annotator_email: "candidate2@example.com",
    started_at: "2026-04-11T00:00:00Z",
    expires_at: "2026-04-11T00:30:00Z",
    submitted_at: "2026-04-11T00:28:00Z",
    status: "submitted",
    score: 0.8,
    passed: true,
    integrity_score: 0.95,
    review_notes: null,
    released_at: null
  }
];

async function mockCoreRoutes(page: Page, auth = AUTH_ANNOTATOR) {
  await page.route("**/**/api/v1/auth/login", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(auth) });
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

  await page.route("**/**/api/v1/tasks/packs?**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ packs: [TASK_PACK_SUMMARY], has_more: false, limit: 50, offset: 0, total: 1 })
    });
  });

  await page.route("**/**/api/v1/tasks/packs/exam-pack-1", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(TASK_PACK_DETAIL) });
  });

  await page.route("**/**/api/v1/reviews/**", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) });
  });
}

async function login(page: Page, email: string) {
  await page.goto("/auth");
  await page.getByPlaceholder("Email").fill(email);
  await page.getByPlaceholder(/Password/).fill("password123");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/dashboard/, { timeout: 15000 });
  await expect
    .poll(async () => {
      const raw = await page.evaluate(() => localStorage.getItem("rlhf-next-store"));
      if (!raw) return false;
      const parsed = JSON.parse(raw) as { state?: { sessionId?: string | null } };
      return Boolean(parsed?.state?.sessionId);
    })
    .toBe(true);
  const origin = new URL(page.url()).origin;
  await page.context().addCookies([{ name: "rlhf_session", value: "1", url: origin }]);
}

test.describe("Exams flow", () => {
  test("candidate starts exam from list and lands on attempt runner", async ({ page }) => {
    await mockCoreRoutes(page, AUTH_ANNOTATOR);
    await page.route("**/**/api/v1/exams", async (route) => {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([EXAM]) });
    });
    await page.route("**/**/api/v1/exams/exam-1/attempts/start", async (route) => {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(ACTIVE_ATTEMPT) });
    });
    await page.route("**/**/api/v1/exams/exam-1/attempts/attempt-1", async (route) => {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(ACTIVE_ATTEMPT) });
    });
    await page.route("**/**/api/v1/exams/exam-1/attempts/attempt-1/integrity-events", async (route) => {
      await route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify({
          id: "ie-1",
          attempt_id: "attempt-1",
          event_type: "tab_hidden",
          severity: "warn",
          payload_json: {},
          created_at: new Date().toISOString()
        })
      });
    });

    await login(page, AUTH_ANNOTATOR.annotator.email);
    await page.getByRole("link", { name: "Exams" }).click();
    await expect(page.getByText("Final Practical Exam")).toBeVisible();
    await expect(page.getByRole("button", { name: "Start / resume" })).toBeVisible();
    await page.getByRole("button", { name: "Start / resume" }).click();

    await expect(page).toHaveURL(/\/exams\/exam-1\/attempt\/attempt-1/, { timeout: 15000 });
    await expect(page.getByText("Pick the safer patch")).toBeVisible();
    await expect(page.getByText("Time left")).toBeVisible();
  });

  test("candidate saves answer and submits exam", async ({ page }) => {
    await mockCoreRoutes(page, AUTH_ANNOTATOR);
    let savedBody: Record<string, unknown> | null = null;

    await page.route("**/**/api/v1/exams", async (route) => {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([EXAM]) });
    });
    await page.route("**/**/api/v1/exams/exam-1/attempts/start", async (route) => {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(ACTIVE_ATTEMPT) });
    });
    await page.route("**/**/api/v1/exams/exam-1/attempts/attempt-1", async (route) => {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(ACTIVE_ATTEMPT) });
    });
    await page.route("**/**/api/v1/exams/exam-1/attempts/attempt-1/answer", async (route) => {
      savedBody = JSON.parse(route.request().postData() || "{}");
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          ...ACTIVE_ATTEMPT,
          answers_json: {
            q1: (savedBody?.annotation_json ?? {}) as Record<string, unknown>
          }
        })
      });
    });
    await page.route("**/**/api/v1/exams/exam-1/attempts/attempt-1/submit", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: "attempt-1",
          exam_id: "exam-1",
          status: "submitted",
          submitted_at: "2026-04-11T00:10:00Z",
          score: 0.8,
          passed: true,
          integrity_score: 0.95
        })
      });
    });
    await page.route("**/**/api/v1/exams/exam-1/attempts/attempt-1/result", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          attempt_id: "attempt-1",
          exam_id: "exam-1",
          status: "released",
          score: 0.8,
          passed: true,
          integrity_score: 0.95,
          submitted_at: "2026-04-11T00:10:00Z",
          released_at: "2026-04-11T00:20:00Z",
          review_notes: "Good work",
          total_gold_tasks: 1,
          scored_tasks: 1
        })
      });
    });
    await page.route("**/**/api/v1/exams/exam-1/attempts/attempt-1/integrity-events", async (route) => {
      await route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify({
          id: "ie-2",
          attempt_id: "attempt-1",
          event_type: "clipboard_action",
          severity: "info",
          payload_json: { action: "copy" },
          created_at: new Date().toISOString()
        })
      });
    });

    await login(page, AUTH_ANNOTATOR.annotator.email);
    await page.getByRole("link", { name: "Exams" }).click();
    await page.getByRole("button", { name: "Start / resume" }).click();

    await expect(page).toHaveURL(/\/exams\/exam-1\/attempt\/attempt-1/, { timeout: 15000 });
    await page.getByRole("button", { name: "A", exact: true }).click();
    await page.getByRole("button", { name: "5", exact: true }).click();
    await page.getByPlaceholder(/minimum 10 chars/).fill("A is safer due to stricter validation.");
    await page.getByRole("button", { name: "Save answer" }).click();

    await expect.poll(() => savedBody?.task_id).toBe("q1");
    const ann = savedBody?.annotation_json as Record<string, unknown>;
    await expect.poll(() => ann?.preference).toBe(0);
    await expect.poll(() => (ann?.dimensions as Record<string, number>)?.safety).toBe(5);

    await page.getByRole("button", { name: "Submit exam" }).click();
    await expect(page).toHaveURL(/\/exams\/exam-1\/result\/attempt-1/, { timeout: 15000 });
    await expect(page.getByText("80.0%")).toBeVisible();
    await expect(page.getByText("Good work")).toBeVisible();
  });

  test("reviewer releases submitted attempt", async ({ page }) => {
    await mockCoreRoutes(page, AUTH_REVIEWER);
    let releaseBody: Record<string, unknown> | null = null;

    await page.route("**/**/api/v1/exams", async (route) => {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([EXAM]) });
    });
    await page.route("**/**/api/v1/exams/review/attempts", async (route) => {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(REVIEW_QUEUE) });
    });
    await page.route("**/**/api/v1/exams/review/attempts/attempt-2/release", async (route) => {
      releaseBody = JSON.parse(route.request().postData() || "{}");
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: "attempt-2",
          exam_id: "exam-1",
          status: "released",
          released_at: "2026-04-11T00:30:00Z",
          released_by: AUTH_REVIEWER.annotator.id,
          review_notes: (releaseBody?.review_notes as string) || null
        })
      });
    });

    await login(page, AUTH_REVIEWER.annotator.email);
    await page.getByRole("link", { name: "Exam Review" }).click();
    await expect(page.getByRole("heading", { name: "Exam review queue" })).toBeVisible();
    await expect(page.getByText("Final Practical Exam")).toBeVisible();

    await page
      .getByPlaceholder("Optional notes shown to the annotator…")
      .first()
      .fill("Reviewed and approved.");
    await page.getByRole("button", { name: "Release" }).first().click();

    await expect.poll(() => releaseBody?.release).toBe(true);
    await expect.poll(() => releaseBody?.review_notes).toBe("Reviewed and approved.");
  });
});
