import { defineConfig, devices } from "@playwright/test";

// The separately started server must be tests/serve_family_routines.py using
// its dedicated synthetic PostgreSQL database. No owner runtime is started here.
export default defineConfig({
  testDir: "./tests",
  testMatch: ["family-routines.spec.ts", "redesign.spec.ts"],
  workers: 1,
  reporter: "list",
  outputDir: "test-results-family-routines",
  use: { baseURL: "http://127.0.0.1:18291", trace: "retain-on-failure" },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    { name: "tablet", use: { ...devices["Desktop Chrome"], viewport: { width: 834, height: 1112 }, isMobile: true, hasTouch: true } },
    { name: "phone", use: { ...devices["Desktop Chrome"], viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true } },
  ],
});
