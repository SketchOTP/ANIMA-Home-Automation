import { defineConfig, devices } from "@playwright/test";

const databaseUrl = process.env.ANIMA_E2E_DATABASE_URL ?? "postgresql://anima:anima_dev_only@127.0.0.1:55432/anima";
const opaUrl = process.env.ANIMA_E2E_OPA_URL ?? "http://127.0.0.1:18181";
const uiPort = process.env.ANIMA_E2E_UI_PORT ?? "18090";

export default defineConfig({
  testDir: "./tests",
  // Dedicated Core/Memory/vault fixtures live in their own explicit configs.
  testIgnore: ["**/h5v.spec.ts", "**/family-routines.spec.ts", "**/knowledge.spec.ts", "**/preferences.spec.ts", "**/household-presence.spec.ts", "**/initiative.spec.ts"],
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  use: { baseURL: `http://127.0.0.1:${uiPort}`, trace: "retain-on-failure" },
  webServer: {
    command: `cd .. && ANIMA_DATABASE_URL=${databaseUrl} ANIMA_OPA_URL=${opaUrl} ANIMA_UI_PORT=${uiPort} ANIMA_UI_STATIC_DIR=ui/dist .venv/bin/python scripts/serve_phase12_h4.py`,
    url: `http://127.0.0.1:${uiPort}/healthz`,
    reuseExistingServer: false,
    timeout: 30_000,
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    { name: "tablet", use: { ...devices["iPad Mini"] } },
    { name: "phone", use: { ...devices["iPhone 13"] } },
  ],
});
