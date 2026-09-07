import { defineConfig } from "@playwright/test";
import { resolve } from "node:path";

export default defineConfig({
  testDir: ".", testMatch: "panels.browser.ts", workers: 1, reporter: "list",
  outputDir: "/tmp/anima-initiative-ring-browser-results",
  use: { baseURL: "http://127.0.0.1:18333", trace: "retain-on-failure" },
  webServer: {
    command: `${JSON.stringify(process.execPath)} ${JSON.stringify(resolve(import.meta.dirname, "../../node_modules/vite/bin/vite.js"))} --config ${JSON.stringify(resolve(import.meta.dirname, "vite.config.ts"))}`,
    url: "http://127.0.0.1:18333", reuseExistingServer: false,
  },
  projects: [
    { name: "desktop", use: { browserName: "chromium", viewport: { width: 1440, height: 1000 } } },
    { name: "tablet", use: { browserName: "chromium", viewport: { width: 834, height: 1112 }, isMobile: true, hasTouch: true } },
    { name: "phone", use: { browserName: "chromium", viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true } },
  ],
});
