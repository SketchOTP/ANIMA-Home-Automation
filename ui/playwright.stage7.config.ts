import { defineConfig, devices } from "@playwright/test";

// Only the guarded isolated Core/PG/OPA learning fixture; no generic discovery.
export default defineConfig({
  testDir: "./tests", testMatch: "stage7-learning.spec.ts", workers: 1,
  reporter: "list", outputDir: "test-results-stage7",
  use: { baseURL: "http://127.0.0.1:18337", trace: "retain-on-failure" },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    { name: "phone", use: { ...devices["Desktop Chrome"], viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true } },
  ],
});
