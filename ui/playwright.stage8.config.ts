import { defineConfig, devices } from "@playwright/test";

// Only the guarded real-store owner-result fixture; never generic discovery.
export default defineConfig({
  testDir: "./tests", testMatch: "stage8-owner-results.spec.ts", workers: 1,
  reporter: "list", outputDir: "test-results-stage8", timeout: 60000,
  use: { baseURL: "http://127.0.0.1:18338", trace: "retain-on-failure" },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    { name: "phone", use: { ...devices["Desktop Chrome"], viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true } },
  ],
});
