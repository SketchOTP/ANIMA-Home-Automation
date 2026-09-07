import { test, expect, type Page } from "@playwright/test";

// Dedicated lead-owned disposable PG/OPA/Graph/Memory fixture only. No route
// mocks, provider calls, seeded observations, or owner runtime writes.
test.beforeEach(async ({ baseURL }) => expect(baseURL).toBe("http://127.0.0.1:18293"));
const panel = (page: Page) => page.locator(".initiative-panel");
async function read(page: Page) {
  const response = await page.request.get("/api/v1/initiative");
  expect(response.ok()).toBe(true); const value = await response.json();
  expect(value.status).toBe("SUCCEEDED"); expect(value.authority).toBe("NONE");
  return value;
}
async function open(page: Page) {
  await page.getByRole("navigation").getByRole("button", { name: "Preferences", exact: true }).click();
  await expect(panel(page).getByRole("heading", { name: "SENTRY initiative", exact: true })).toBeVisible();
  await expect(panel(page).getByRole("button", { name: "Save initiative policy" })).toBeEnabled();
}

test("real Core persists versioned initiative config and reloads without inventing observations", async ({ page }, info) => {
  const errors: string[] = []; page.on("pageerror", error => errors.push(error.message));
  await page.goto("/auth/login"); await expect(page.getByRole("heading", { name: /Welcome,/ })).toBeVisible();
  const before = await read(page); expect(before.can_edit).toBe(true);
  expect(before.readiness.observed_local_days).toBe(0); expect(before.readiness.first_observed_at).toBeNull();
  await open(page);
  const days = before.config.learning_days === 6 ? 7 : 6;
  await panel(page).getByRole("spinbutton", { name: "Learning period" }).fill(String(days));
  await panel(page).getByRole("spinbutton", { name: "Routine review interval" }).fill("4");
  await panel(page).getByRole("switch", { name: "Always notify: Ring doorbell", exact: true }).check();
  await panel(page).getByRole("switch", { name: "Optional proactive notifications", exact: true }).check();
  await panel(page).getByRole("button", { name: "Save initiative policy" }).click();
  await expect(panel(page).getByRole("status").filter({ hasText: "Initiative settings saved" })).toBeVisible();
  const saved = await read(page);
  expect(saved.config_version).toMatch(/^[\da-f-]{36}$/); expect(saved.config_version).not.toBe(before.config_version);
  expect(saved.config.learning_days).toBe(days); expect(saved.config.routine_review_days).toBe(4);
  expect(saved.config.always_notify).toContain("household.ring.doorbell"); expect(saved.config.proactive_enabled).toBe(true);
  expect(saved.readiness.ready).toBe(false); expect(saved.proactive_eligible).toBe(false);
  expect(saved.readiness.observed_local_days).toBe(0); expect(saved.readiness.elapsed_seconds).toBe(0);
  expect(saved.readiness.first_observed_at).toBeNull(); expect(saved.readiness.last_observed_at).toBeNull();
  await page.reload(); await open(page);
  await expect(panel(page).getByRole("spinbutton", { name: "Learning period" })).toHaveValue(String(days));
  await expect(panel(page).getByRole("switch", { name: "Always notify: Ring doorbell", exact: true })).toBeChecked();
  await expect(panel(page).getByText("Waiting for observations", { exact: true })).toBeVisible();
  await expect(panel(page).getByText("Automatic wake disabled", { exact: true })).toBeVisible();
  await expect(panel(page).getByText("No learned suggestions recorded.", { exact: false })).toBeVisible();
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
  await panel(page).screenshot({ path: info.outputPath("real-pg-initiative-no-observations.png") });
  // A second real version turns optional initiative back off. No worker is run.
  await panel(page).getByRole("switch", { name: "Optional proactive notifications", exact: true }).uncheck();
  await panel(page).getByRole("button", { name: "Save initiative policy" }).click();
  await expect(panel(page).getByRole("status").filter({ hasText: "Initiative settings saved" })).toBeVisible();
  const disabled = await read(page); expect(disabled.config_version).not.toBe(saved.config_version);
  expect(disabled.config.proactive_enabled).toBe(false); expect(disabled.readiness.observed_local_days).toBe(0);
  await page.reload(); await open(page);
  await expect(panel(page).getByRole("switch", { name: "Optional proactive notifications", exact: true })).not.toBeChecked();
  expect(errors).toEqual([]);
});
