import { defineConfig, devices } from "@playwright/test";

// Hardcoding the Windows venv path breaks the CI runner (bash strips the
// backslashes). Resolve per platform.
const pythonBin =
  process.platform === "win32" ? ".venv\\Scripts\\python.exe" : ".venv/bin/python";

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  use: {
    baseURL: "http://127.0.0.1:5173",
    trace: "on-first-retry",
  },
  webServer: [
    {
      command: `${pythonBin} app.py`,
      port: 5000,
      timeout: 120_000,
      reuseExistingServer: !process.env.CI,
      env: { FLASK_ENV: "development", PORT: "5000" },
    },
    {
      command: "npm run dev -- --host 127.0.0.1 --port 5173",
      port: 5173,
      timeout: 120_000,
      reuseExistingServer: !process.env.CI,
    },
  ],
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
