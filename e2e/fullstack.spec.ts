import { expect, test } from "@playwright/test";

const TEST_EMAIL = "testsprite@example.com";
const TEST_PASSWORD = "TestSprite1!";

test.describe("full-stack (real backend via Vite proxy)", () => {
  test.beforeAll(async ({ request }) => {
    const health = await request.get("/api/v1/health");
    if (!health.ok()) {
      test.skip(true, "Backend not running on :5000 (start python app.py)");
    }
    await request.post("/api/v1/auth/register", {
      data: { email: TEST_EMAIL, password: TEST_PASSWORD },
      failOnStatusCode: false,
    });
  });

  test("health via proxy", async ({ request }) => {
    const res = await request.get("/api/v1/health");
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.status).toBeDefined();
  });

  test("editor loads and runs Python against real API", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByText("AI Code Mentor")).toBeVisible();
    await page.getByRole("button", { name: "Run" }).click();
    await expect(page.locator(".output-pane")).toContainText("Hello World", {
      timeout: 30_000,
    });
  });

  test("auth login shows user badge", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: "Sign in" }).click();
    await page.locator("#auth-email").fill(TEST_EMAIL);
    await page.locator("#auth-password").fill(TEST_PASSWORD);
    await page.locator("button.auth-submit").click();
    await expect(page.locator(".auth-user-badge")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByRole("button", { name: "Sign out" })).toBeVisible();
  });

  test("theme toggle changes document class", async ({ page }) => {
    await page.goto("/");
    const html = page.locator("html");
    const before = await html.getAttribute("class");
    const themeBtn = page.getByRole("button", { name: "Toggle dark/light" });
    if (await themeBtn.count()) {
      await themeBtn.click();
      const after = await html.getAttribute("class");
      expect(after).not.toBe(before);
    }
  });
});
