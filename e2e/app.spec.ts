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
      }),
    });
  });

  await page.goto("/");
  await expect(page.getByText("AI Code Mentor")).toBeVisible();
  await expect(page.getByRole("button", { name: "Run Code" })).toBeEnabled();

  await page.getByRole("button", { name: "Run Code" }).click();
  await expect(page.getByText("hello from mocked backend")).toBeVisible();
});
