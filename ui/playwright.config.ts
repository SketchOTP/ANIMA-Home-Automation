import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  reporter: [["list"]],
  use: { baseURL: "http://127.0.0.1:18090", trace: "retain-on-failure" },
  webServer: {
    command: "cd .. && ANIMA_UI_TEST_AUTH=1 ANIMA_UI_PORT=18090 ANIMA_UI_STATIC_DIR=ui/dist uv run anima-ui",
    url: "http://127.0.0.1:18090/healthz",
    reuseExistingServer: false,
    timeout: 30_000,
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    { name: "tablet", use: { ...devices["iPad Mini"] } },
    { name: "phone", use: { ...devices["iPhone 13"] } },
  ],
});
