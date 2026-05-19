import { expect, test } from "@playwright/test";

test("renders editor and can run code with mocked API", async ({ page }) => {
  await page.route("**/api/v1/analyze", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ok: true,
        language: "python",
        summary: { line_count: 1, issue_count: 0 },
        issues: [],
        execution: {
          stdout: "hello from mocked backend\n",
          stderr: "",
          returncode: 0,
          timed_out: false,
          tool_missing: false,
          error: null,
        },
        ai_mentor_feedback: "LOOKS_GOOD",
        ai_mentor_status: "ok",
      }),
    });
  });

  await page.goto("/");
  await expect(page.getByText("AI Code Mentor")).toBeVisible();
  await expect(page.getByRole("button", { name: "Run" })).toBeEnabled();

  await page.getByRole("button", { name: "Run" }).click();
  await expect(page.getByText("hello from mocked backend")).toBeVisible();
});

test("shows a clear sandbox unavailable message", async ({ page }) => {
  await page.route("**/api/v1/analyze", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ok: true,
        language: "python",
        summary: { line_count: 1, issue_count: 0 },
        issues: [],
        execution: {
          stdout: "",
          stderr: "Docker SDK is not installed on this server.",
          returncode: -1,
          timed_out: false,
          tool_missing: true,
          error: {
            type: "SandboxUnavailable",
            message: "Docker SDK is not installed on this server.",
            explanation: "Untrusted code execution requires a sandbox.",
          },
        },
        ai_mentor_feedback: "AI_MENTOR_DISABLED",
        ai_mentor_status: "disabled",
      }),
    });
  });

  await page.goto("/");
  await page.getByRole("button", { name: "Run" }).click();
  await expect(page.getByText("Sandbox unavailable: Docker is not available")).toBeVisible();
  await expect(page.getByText("AI Mentor is disabled.")).toBeVisible();
});

const aiFailureCases = [
  {
    status: "api_error",
    feedback: "AI_MENTOR_API_ERROR",
    text: "AI Mentor could not reach Gemini.",
  },
  {
    status: "quota_exceeded",
    feedback: "AI_MENTOR_QUOTA_EXCEEDED",
    text: "AI Mentor quota is exhausted.",
  },
  {
    status: "bad_response",
    feedback: "AI_MENTOR_BAD_RESPONSE",
    text: "AI Mentor returned an unreadable response.",
  },
];

for (const aiCase of aiFailureCases) {
  test(`shows ${aiCase.status} AI Mentor state`, async ({ page }) => {
    await page.route("**/api/v1/analyze", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          ok: true,
          language: "python",
          summary: { line_count: 1, issue_count: 0 },
          issues: [],
          execution: {
            stdout: "hello\n",
            stderr: "",
            returncode: 0,
            timed_out: false,
            tool_missing: false,
            error: {},
          },
          ai_mentor_feedback: aiCase.feedback,
          ai_mentor_status: aiCase.status,
        }),
      });
    });

    await page.goto("/");
    await page.getByRole("button", { name: "Run" }).click();
    await expect(page.getByText(aiCase.text)).toBeVisible();
  });
}
