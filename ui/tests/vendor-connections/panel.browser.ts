import { expect, test, type Page } from "@playwright/test";

// Contract fixtures only. No connection to the production Core or vendor apps.
const route = "**/api/v1/vendor-events/status";
const waiting = () => ({ configured: false, enabled: false, state: "WAITING_APP_SETUP", gates: ["WAITING_APP_SETUP"],
  vendors: ["tapo", "wansview"].map(vendor => ({ vendor, configured: false, enabled: false, state: "WAITING_APP_SETUP",
    gates: vendor === "tapo" ? ["HA_LOCK_MAPPING_REQUIRED", "SOURCE_SAMPLE_REQUIRED"]
      : ["LIVE_FORMAT_UNQUALIFIED", "WAITING_APP_SETUP", "SOURCE_PRIVACY_UNQUALIFIED", "CANONICAL_MAPPING_REQUIRED", "RELAY_DISABLED"], last_receipt_at: null })) });
const ready = () => ({ configured: true, enabled: true, state: "READY", gates: [],
  vendors: ["tapo", "wansview"].map(vendor => ({ vendor, configured: true, enabled: true, state: "READY", gates: [], last_receipt_at: null as string | null })) });
const card = (page: Page, name = "Tapo DL110") => page.getByRole("article", { name, exact: true });
async function fixture(page: Page, data: unknown) {
  const calls: string[] = [];
  await page.route(route, request => { calls.push(request.request().method()); return request.fulfill({ json: data }); });
  await page.goto("/");
  await expect(page.getByRole("button", { name: "Refresh status", exact: true })).toBeEnabled();
  return calls;
}

test("waiting app setup stays disabled, checklist is actionable without sending", async ({ page }, testInfo) => {
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  const calls = await fixture(page, waiting());
  await expect(page.getByText("Declared mock responses only — not live device evidence.")).toBeVisible();
  for (const name of ["Tapo DL110", "Wansview"]) {
    const target = card(page, name);
    await expect(target.locator(".vendor-state")).toHaveText("Waiting for app setup");
    await expect(target.getByRole("list", { name: `${name} readiness` })).toContainText("Disabled");
    await expect(target.locator(".vendor-receipt")).toContainText("No receipt recorded");
    await target.getByText(`Setup checklist for ${name}`, { exact: true }).click();
    await expect(target).toContainText("Official app setup.");
    await expect(target).toContainText(name === "Tapo DL110" ? "Verified source setup." : "Private relay setup.");
    await expect(target.getByRole("list", { name: `${name} backend setup gates` })).toContainText(name === "Tapo DL110" ? "Verified Home Assistant lock mapping" : "Live notification format needs qualification");
    await expect(target).toContainText("Observe, then refresh.");
    await expect(target.locator("input, textarea, select, img, video, iframe")).toHaveCount(0);
    await target.getByText(`Setup checklist for ${name}`, { exact: true }).click();
  }
  expect(calls.every(method => method === "GET")).toBe(true);
  await expect(page.locator(".vendor-connections")).not.toContainText("Connected");
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("waiting-app-setup-not-live.png"), fullPage: true });
  expect(errors).toEqual([]);
  await expect(page.locator("vite-error-overlay")).toHaveCount(0);
});

test("ready configuration is not live receipt; refresh reports only actual per-vendor receipt", async ({ page }, testInfo) => {
  const value = ready();
  const calls = await fixture(page, value);
  await expect(card(page).locator(".vendor-state")).toHaveText("Ready to receive");
  await expect(card(page).locator(".vendor-receipt")).toContainText("No receipt recorded");
  value.vendors[0].state = "RECEIVED";
  value.vendors[0].last_receipt_at = "2026-09-07T03:02:45.789328Z";
  await page.route(route, request => { calls.push(request.request().method()); return request.fulfill({ json: value }); });
  await page.getByRole("button", { name: "Refresh status" }).click();
  await expect(card(page).locator(".vendor-state")).toHaveText("Event received");
  await expect(card(page).locator("time")).toHaveAttribute("datetime", value.vendors[0].last_receipt_at);
  await expect(card(page, "Wansview").locator(".vendor-state")).toHaveText("Ready to receive");
  await expect(card(page, "Wansview").locator("time")).toHaveCount(0);
  await card(page).getByText("Source & time quality", { exact: true }).click();
  await expect(card(page)).toContainText("Source event time is not supplied");
  await expect(card(page)).toContainText("does not establish who unlocked");
  await expect(card(page)).toContainText("does not prove continuing delivery");
  expect(calls.every(method => method === "GET")).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("receipt-is-not-physical-state.png"), fullPage: true });
});

test("disabled intake retains historical receipt without advertising readiness", async ({ page }) => {
  const value = ready(); value.enabled = false; value.state = "DISABLED";
  value.vendors[0] = { ...value.vendors[0], state: "DISABLED", enabled: false, last_receipt_at: "2020-01-01T00:00:00Z" };
  await fixture(page, value);
  await expect(card(page).locator(".vendor-state")).toHaveText("Disabled");
  await expect(card(page).locator("time")).toHaveAttribute("datetime", "2020-01-01T00:00:00Z");
  await expect(card(page)).toContainText("Intake is disabled");
  await expect(card(page, "Wansview").locator(".vendor-state")).toHaveText("Disabled");
});

test("missing vendor is unknown, not a copy of aggregate or other vendor status", async ({ page }) => {
  const value = ready(); value.vendors = [value.vendors[0]];
  await fixture(page, value);
  await expect(card(page).locator(".vendor-state")).toHaveText("Ready to receive");
  await expect(card(page, "Wansview").locator(".vendor-state")).toHaveText("Status unavailable");
  await expect(card(page, "Wansview").locator(".vendor-readiness")).toContainText("Not reported");
});

test("refresh failure clears previous readiness and never renders backend error text", async ({ page }) => {
  await fixture(page, ready());
  await page.route(route, request => request.fulfill({ status: 503, json: { detail: "PRIVATE_SERVER_TOKEN_SENTINEL" } }));
  await page.getByRole("button", { name: "Refresh status" }).click();
  await expect(page.getByRole("alert")).toContainText("Earlier status has been cleared");
  await expect(card(page).locator(".vendor-state")).toHaveText("Status unavailable");
  await expect(page.locator("body")).not.toContainText("PRIVATE_SERVER_TOKEN_SENTINEL");
});

for (const code of [401, 403, 404]) {
  test(`HTTP ${code} is explicit and cannot pretend to be disabled or connected`, async ({ page }) => {
    await page.route(route, request => request.fulfill({ status: code, json: { detail: "PRIVATE_ERROR_SENTINEL" } }));
    await page.goto("/");
    await expect(page.getByRole("alert")).toContainText(code === 401 ? "Fixture session expired" : code === 403 ? "not available to this account" : "not available in this build");
    if (code === 401) await expect(page.getByRole("heading", { name: "Vendor app notifications" })).toHaveCount(0);
    else await expect(card(page).locator(".vendor-state")).toHaveText("Status unavailable");
    await expect(page.locator("body")).not.toContainText("PRIVATE_ERROR_SENTINEL");
  });
}

test("malformed or duplicate status fails closed and extra fields are never displayed", async ({ page }) => {
  const value = ready();
  await fixture(page, { ...value, vendors: [value.vendors[0], value.vendors[0]], token: "PRIVATE_FIELD_SENTINEL" });
  await expect(page.getByRole("alert")).toContainText("could not be verified");
  await expect(card(page).locator(".vendor-state")).toHaveText("Status unavailable");
  await page.route(route, request => request.fulfill({ json: { ...value, token: "PRIVATE_FIELD_SENTINEL",
    vendors: value.vendors.map(item => ({ ...item, gates: ["PRIVATE_GATE_SENTINEL"], notification: "PRIVATE_NOTIFICATION_SENTINEL", image_url: "https://invalid.example/image.jpg" })) } }));
  await page.getByRole("button", { name: "Refresh status" }).click();
  await expect(card(page).locator(".vendor-state")).toHaveText("Setup required");
  await expect(page.locator("body")).not.toContainText(/PRIVATE_(FIELD|GATE|NOTIFICATION)_SENTINEL/);
  await expect(page.locator(".vendor-connections img")).toHaveCount(0);
});

test("receipt without a timestamp and invalid timezone-free timestamps cannot appear verified", async ({ page }) => {
  const value = ready(); value.vendors[0].state = "RECEIVED";
  await fixture(page, value);
  await expect(card(page).locator(".vendor-state")).toHaveText("Status unavailable");
  value.vendors[0].last_receipt_at = "2026-09-07T03:02:45";
  await page.route(route, request => request.fulfill({ json: value }));
  await page.getByRole("button", { name: "Refresh status" }).click();
  await expect(page.getByRole("alert")).toContainText("could not be verified");
  await expect(card(page).locator("time")).toHaveCount(0);
});

test("keyboard disclosure and light/system themes preserve layout", async ({ page }, testInfo) => {
  await fixture(page, waiting());
  const summary = card(page).getByText("Setup checklist for Tapo DL110", { exact: true });
  await summary.focus(); await page.keyboard.press("Enter");
  await expect(card(page).locator(".vendor-setup")).toHaveAttribute("open", "");
  await page.keyboard.press("Enter");
  for (const theme of ["light", "system"]) {
    await page.getByLabel("Fixture theme").selectOption(theme);
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  }
  await page.emulateMedia({ colorScheme: "light", reducedMotion: "reduce" });
  await page.screenshot({ path: testInfo.outputPath("system-light-not-live.png"), fullPage: true });
});

test("pending fetch aborts on unmount and cannot repopulate an expired panel", async ({ page }) => {
  let release!: () => void;
  const pending = new Promise<void>(resolve => { release = resolve; });
  await page.route(route, async request => { await pending; await request.fulfill({ json: ready() }).catch(() => {}); });
  await page.goto("/");
  await expect(page.getByRole("button", { name: "Checking status…", exact: true })).toBeDisabled();
  await page.getByRole("button", { name: "Hide fixture panel" }).click();
  release();
  await expect(page.getByRole("heading", { name: "Vendor app notifications" })).toHaveCount(0);
  await expect(page.getByRole("alert")).toHaveCount(0);
});
