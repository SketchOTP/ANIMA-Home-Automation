import { defineConfig, devices } from "@playwright/test";

// Start tests/serve_household_context.py with disposable PostgreSQL and real OPA.
export default defineConfig({
  testDir: "./tests",
  testMatch: ["preferences.spec.ts", "household-presence.spec.ts"],
  workers: 1,
  reporter: "list",
  outputDir: "test-results-household-context",
  use: { baseURL: "http://127.0.0.1:18293", trace: "retain-on-failure" },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    { name: "tablet", use: { ...devices["Desktop Chrome"], viewport: { width: 834, height: 1112 }, isMobile: true, hasTouch: true } },
    { name: "phone", use: { ...devices["Desktop Chrome"], viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true } },
  ],
});
