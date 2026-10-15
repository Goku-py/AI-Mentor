import { defineConfig, devices } from "@playwright/test";
import { existsSync } from "node:fs";

const pythonCandidates =
  process.platform === "win32"
    ? [".venv\\Scripts\\python.exe", "python", "python3"]
    : [".venv/bin/python", "python3", "python"];

const pythonBin = pythonCandidates.find((bin) => existsSync(bin)) ?? pythonCandidates[0];

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
