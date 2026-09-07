import { defineConfig, devices } from "@playwright/test";

// Start tests/serve_knowledge_ui.py separately. It prints an ephemeral loopback
// port and uses a temporary native filesystem, synthetic login and policy.
// Never point this suite at the owner service: the journey writes fixture notes.
const baseURL = process.env.ANIMA_KNOWLEDGE_TEST_URL;
if (!baseURL || !/^http:\/\/127\.0\.0\.1:\d+$/.test(baseURL)) {
  throw new Error("Set ANIMA_KNOWLEDGE_TEST_URL to the isolated fixture loopback URL");
}
export default defineConfig({
  testDir: "./tests", testMatch: "knowledge.spec.ts", workers: 1,
  reporter: "list", outputDir: "test-results-knowledge",
  use: { baseURL, trace: "retain-on-failure" },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 1000 } } },
    { name: "tablet", use: { ...devices["Desktop Chrome"], viewport: { width: 834, height: 1112 } } },
    { name: "phone", use: { ...devices["Desktop Chrome"], viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true } },
  ],
});
