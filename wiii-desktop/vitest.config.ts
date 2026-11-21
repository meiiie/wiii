import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    // The 2.7k-test single-fork suite can spend ~30s transforming Plotly and
    // Recharts modules on Windows even though focused runs finish in seconds.
    // Keep the guard finite while avoiding load-dependent false failures.
    testTimeout: 45_000,
    setupFiles: ["src/__tests__/setup.ts"],
    // Keep vitest's default excludes and add the Playwright spec folder —
    // playwright/*.spec.ts uses @playwright/test's test.describe(), which
    // throws when collected by vitest. Those files run via the Playwright
    // runner in a separate job.
    exclude: [
      "**/node_modules/**",
      "**/dist/**",
      "**/cypress/**",
      "**/.{idea,git,cache,output,temp}/**",
      "**/{karma,rollup,webpack,vite,vitest,jest,ava,babel,nyc,cypress,tsup,build}.config.*",
      "**/playwright/**",
      "**/e2e/**",
    ],
    pool: "forks",
    fileParallelism: true,
    maxWorkers: 4,
    coverage: {
      provider: "v8",
      reporter: ["text", "html", "json-summary"],
      include: ["src/**/*.{ts,tsx}"],
      exclude: [
        "src/__tests__/**",
        "src/**/*.test.{ts,tsx}",
        "src/vite-env.d.ts",
      ],
      thresholds: {
        // Ratchet: about 2 points under what the full src include set measures
        // (64.2 / 57.3 / 62.4 / 65.8 on 2026-11-21). Raise these as coverage
        // grows; never lower them or narrow the measured source scope.
        statements: 62,
        branches: 55,
        functions: 60,
        lines: 63,
      },
    },
  },
});
