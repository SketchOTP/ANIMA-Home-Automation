import { defineConfig, devices } from "@playwright/test";

// Explicit real Core/PG/OPA plus synthetic HA transport; never generic/owner Core.
export default defineConfig({
  testDir: "./tests",
  testMatch: "stage6-owner-workflows.spec.ts",
  workers: 1,
  reporter: "list",
  outputDir: "test-results-stage6",
  use: { baseURL: "http://127.0.0.1:18336", trace: "retain-on-failure" },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    { name: "phone", use: { ...devices["Desktop Chrome"], viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true } },
  ],
});
