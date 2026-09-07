import { defineConfig, devices } from "@playwright/test";
import { resolve } from "node:path";

const uiRoot = resolve(import.meta.dirname, "../..");
export default defineConfig({
  testDir: ".", testMatch: "panel.browser.ts", workers: 1,
  outputDir: "/tmp/anima-vendor-panel-results", reporter: "list",
  use: { baseURL: "http://127.0.0.1:18329", trace: "retain-on-failure" },
  webServer: {
    command: `"${process.execPath}" "${resolve(uiRoot, "node_modules/vite/bin/vite.js")}" --config "${resolve(import.meta.dirname, "vite.config.ts")}"`,
    url: "http://127.0.0.1:18329", reuseExistingServer: false,
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    { name: "tablet", use: { ...devices["Desktop Chrome"], viewport: { width: 834, height: 1112 }, isMobile: true, hasTouch: true } },
    { name: "phone", use: { ...devices["Desktop Chrome"], viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true } },
  ],
});
