import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  use: {
    baseURL: "http://127.0.0.1:5173",
    trace: "on-first-retry",
  },
  webServer: [
    {
      command: "python app.py",
      port: 5000,
      timeout: 120_000,
      reuseExistingServer: true,
      env: { FLASK_ENV: "development", PORT: "5000" },
    },
    {
      command: "npm run dev -- --host 127.0.0.1 --port 5173",
      port: 5173,
      timeout: 120_000,
      reuseExistingServer: true,
    },
  ],
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
