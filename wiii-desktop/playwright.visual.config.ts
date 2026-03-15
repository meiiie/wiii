import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./playwright",
  testMatch: ["visual-runtime.spec.ts"],
  fullyParallel: false,
  workers: 1,
  timeout: 180_000,
  expect: {
    timeout: 15_000,
  },
  reporter: [["list"]],
  use: {
    baseURL: "http://127.0.0.1:1420",
    browserName: "chromium",
    headless: true,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  webServer: [
    {
      command: "node scripts/start-visual-backend.mjs",
      url: "http://127.0.0.1:8001/api/v1/health/live",
      reuseExistingServer: true,
      timeout: 180_000,
    },
    {
      command: "node scripts/start-visual-frontend.mjs",
      url: "http://127.0.0.1:1420",
      reuseExistingServer: true,
      timeout: 180_000,
    },
  ],
});
