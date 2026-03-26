import { expect, test } from "@playwright/test";

test("renders auth page", async ({ page }) => {
  await page.goto("/auth");
  await expect(page.getByRole("heading", { name: "RLHF Annotation Studio" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Login" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Register" })).toBeVisible();
});

test("login, load pack, and open task workflow", async ({ page }) => {
  await page.route("**/api/v1/tasks/packs", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        packs: [
          {
            id: "pack-1",
            slug: "debugging-exercises-python",
            name: "Python Debugging",
            description: "Debug Python snippets",
            language: "python",
            task_count: 1,
            created_at: "2026-01-01T00:00:00Z"
          }
        ]
      })
    });
  });

  await page.route("**/api/v1/tasks/packs/*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: "pack-1",
        slug: "debugging-exercises-python",
        name: "Python Debugging",
        description: "Debug Python snippets",
        language: "python",
        task_count: 1,
        created_at: "2026-01-01T00:00:00Z",
        tasks_json: [
          {
            id: "task-1",
            type: "comparison",
            title: "Fix buggy function",
            prompt: "Find the better fix.",
            responses: [
              { label: "A", text: "Use copy.deepcopy" },
              { label: "B", text: "Use list()" }
            ],
            dimensions: [{ name: "correctness", description: "Correctness", scale: 5 }]
          }
        ]
      })
    });
  });

  await page.route("**/api/v1/auth/login", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        token: "fake-token",
        annotator: {
          id: "f5f5432e-57cd-4b22-84df-a35395f60529",
          name: "E2E User",
          email: "e2e@example.com",
          phone: null
        },
        session_id: "4b94db28-59c6-4716-a890-1c7e58eca66d"
      })
    });
  });

  await page.route("**/api/v1/sessions/*/workspace", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          session_id: "4b94db28-59c6-4716-a890-1c7e58eca66d",
          annotator_id: "f5f5432e-57cd-4b22-84df-a35395f60529",
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
      body: JSON.stringify({ ok: true })
    });
  });

  await page.route("**/api/v1/tasks/validate", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ok: true,
        strict_mode: false,
        total_tasks: 9,
        valid_tasks: 9,
        issues: []
      })
    });
  });

  await page.goto("/auth");
  await page.getByPlaceholder("Email").fill("e2e@example.com");
  await page.getByPlaceholder("Password").fill("password123");
  await page.getByRole("button", { name: "Sign in" }).click();

  await expect(page).toHaveURL(/\/dashboard/);
  await expect(page.getByRole("heading", { name: "Task Library" })).toBeVisible();

  await page.getByRole("button", { name: "Load and Start" }).first().click();
  await expect(page).toHaveURL(/\/task\/0/);
  await expect(page.getByRole("heading", { level: 3, name: "Prompt" })).toBeVisible();
});

