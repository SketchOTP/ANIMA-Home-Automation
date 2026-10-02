import { defineConfig, devices } from "@playwright/test";

// Separately launched guarded real-PG/current-OPA fixture. Never owner Core.
export default defineConfig({
  testDir: "./tests",
  testMatch: "stage5-owner-workflows.spec.ts",
  workers: 1,
  reporter: "list",
  outputDir: "test-results-stage5",
  use: { baseURL: "http://127.0.0.1:18335", trace: "retain-on-failure" },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    { name: "phone", use: { ...devices["Desktop Chrome"], viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true } },
  ],
});
