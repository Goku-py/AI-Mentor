import { expect, test } from "@playwright/test";

// Mirrors the real POST /analyze payload (app_pkg/blueprints/api/routes.py):
// { success, output, error, meta: { language, executionTimeMs, issues,
//   ai_mentor_feedback, ai_mentor_status, mismatch, execution } }
const analyzeResponse = (meta: Record<string, unknown>, rest: Record<string, unknown> = {}) => ({
  success: true,
  output: "",
  error: "",
  ...rest,
  meta: { language: "python", executionTimeMs: 1, ...meta },
});

test("renders editor and can run code with mocked API", async ({ page }) => {
  await page.route("**/api/v1/analyze", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(
        analyzeResponse({
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
      ),
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
      body: JSON.stringify(
        analyzeResponse({
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
      ),
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

test("language switch changes code and runs the new language", async ({ page }) => {
  await page.goto("/");
  const editor = page.locator("textarea.code-textarea");

  await expect(editor).toHaveValue(/print\("Hello World!"\)/);

  await page.getByLabel("Select programming language").selectOption("javascript");
  await expect(editor).toHaveValue(/console.log\("Hello World!"\)/);

  await page.route("**/api/v1/analyze", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(
        analyzeResponse(
          {
            language: "javascript",
            issues: [],
            execution: { stdout: "JS output\n", stderr: "", returncode: 0 },
            ai_mentor_feedback: "",
            ai_mentor_status: "ok",
          },
        ),
      ),
    });
  });

  await page.getByRole("button", { name: "Run" }).click();
  await expect(page.getByText("JS output")).toBeVisible();
});

test("file upload shows toast for unsupported file type", async ({ page }) => {
  await page.goto("/");

  const fileInput = page.locator("input[type=file]");
  await fileInput.setInputFiles({
    name: "test.rs",
    mimeType: "text/plain",
    buffer: Buffer.from('fn main() { println!("hi"); }'),
  });

  await expect(page.getByText("Unsupported file type: rs")).toBeVisible({ timeout: 3000 });
});

test("static issues alone do not raise an execution error banner", async ({ page }) => {
  await page.route("**/api/v1/analyze", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(
        analyzeResponse({
          issues: [{ severity: "error", line: 1, message: "unused variable" }],
          execution: { stdout: "ran fine\n", stderr: "", returncode: 0 },
          ai_mentor_feedback: "",
          ai_mentor_status: "ok",
        }),
      ),
    });
  });

  await page.goto("/");
  await page.getByRole("button", { name: "Run" }).click();

  await expect(page.getByText("ran fine")).toBeVisible();
  await expect(page.getByText("unused variable")).toBeVisible();
  await expect(page.getByText("An execution error occurred.")).toHaveCount(0);
});

for (const aiCase of aiFailureCases) {
  test(`shows ${aiCase.status} AI Mentor state`, async ({ page }) => {
    await page.route("**/api/v1/analyze", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(
          analyzeResponse({
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
        ),
      });
    });

    await page.goto("/");
    await page.getByRole("button", { name: "Run" }).click();
    await expect(page.getByText(aiCase.text)).toBeVisible();
  });
}

/* ---- Regression: typing in the auth modal must not lose focus ----
   The focus-management effect used to depend on the `onClose` prop. App passed
   a fresh arrow every render, so each keystroke re-ran it and yanked focus
   back to the email field: typing "hunter2secret" into password produced
   password="h", email="unter2secret". These tests use keyboard.type() and
   never fill(), because fill() bypasses the keystroke path entirely. */

const openAuthModal = async (page: import("@playwright/test").Page) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Sign in" }).first().click();
  await expect(page.locator("#auth-email")).toBeVisible();
  await expect(page.locator("#auth-email")).toBeFocused();
};

test("typed password lands entirely in the password field", async ({ page }) => {
  await openAuthModal(page);

  const password = page.locator("#auth-password");
  await password.click();
  await page.keyboard.type("hunter2secret");

  await expect(password).toHaveValue("hunter2secret");
  await expect(password).toBeFocused();
  await expect(page.locator("#auth-email")).toHaveValue("");
});

test("typing email then password never moves focus backwards", async ({ page }) => {
  await openAuthModal(page);

  await page.keyboard.type("learner@example.com");
  await expect(page.locator("#auth-email")).toHaveValue("learner@example.com");
  await expect(page.locator("#auth-email")).toBeFocused();

  await page.locator("#auth-password").click();
  await page.keyboard.type("s3cretpass");

  await expect(page.locator("#auth-email")).toHaveValue("learner@example.com");
  await expect(page.locator("#auth-password")).toHaveValue("s3cretpass");
  await expect(page.locator("#auth-password")).toBeFocused();
});

test("login accepts a legacy password that fails the registration rule", async ({ page }) => {
  await page.route("**/api/v1/auth/login", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ ok: true, user: { id: 1, email: "legacy@example.com", role: "student" }, access_token: "t" }),
    });
  });

  await openAuthModal(page);
  await page.keyboard.type("legacy@example.com");
  await page.locator("#auth-password").click();
  await page.keyboard.type("password"); // 8 chars, no digit, no symbol
  await page.getByRole("button", { name: "Sign In", exact: true }).last().click();

  await expect(page.locator(".auth-modal")).toHaveCount(0);
  await expect(page.getByText("legacy")).toBeVisible();
});

test("register still enforces the password strength rule", async ({ page }) => {
  await openAuthModal(page);
  await page.getByRole("tab", { name: "Create Account" }).click();

  // Focus sits on the tab after switching, so target the fields explicitly.
  await page.locator("#auth-email").click();
  await page.keyboard.type("new@example.com");
  await page.locator("#auth-password").click();
  await page.keyboard.type("password"); // fails the strength rule
  await page.getByRole("button", { name: "Create Account" }).last().click();

  await expect(page.getByText("Password must contain at least one digit or special character.")).toBeVisible();
});

test("a non-JSON auth response surfaces a recoverable error instead of a frozen modal", async ({ page }) => {
  await page.route("**/api/v1/auth/login", async (route) => {
    await route.fulfill({ status: 502, contentType: "text/html", body: "<html>502 Bad Gateway</html>" });
  });

  await openAuthModal(page);
  await page.keyboard.type("someone@example.com");
  await page.locator("#auth-password").click();
  await page.keyboard.type("s3cretpass");
  await page.getByRole("button", { name: "Sign In", exact: true }).last().click();

  await expect(page.getByRole("alert")).toBeVisible();
  await expect(page.getByText("non-JSON")).toBeVisible();
  await expect(page.getByRole("button", { name: "Sign In", exact: true }).last()).toBeEnabled();
});