import { test, expect } from "@playwright/test";

// Component/transport contract fixtures only. Real Core/OPA/PostgreSQL presence
// binding is independently exercised in test_household_presence_postgres.py.
test.beforeEach(async ({ page, baseURL }) => {
  expect(baseURL).toBe("http://127.0.0.1:18293");
  await page.goto("/auth/login");
  await expect(page.getByRole("heading", { name: /Welcome,/ })).toBeVisible();
});
const person = "00000000-0000-0000-0000-000000000002";
const source = "00000000-0000-0000-0000-000000000003";
const empty = { items: [{ person_id: person, value: "UNKNOWN", status: "UNKNOWN", binding_status: "UNCONFIGURED", signals: [] }], members: [{ person_id: person, name: "Synthetic member" }], can_edit: true, next_cursor: null };

test("unconfigured presence is explicit, responsive, and never inferred from routines", async ({ page }, info) => {
  await page.route("**/api/v1/presence?*", route => route.fulfill({ json: empty }));
  await page.route("**/api/v1/presence/sources?*", route => route.fulfill({ json: { items: [], next_cursor: null } }));
  await page.getByRole("navigation").getByRole("button", { name: "Routines", exact: true }).click();
  const panel = page.getByRole("region", { name: "Household presence", exact: true });
  await expect(panel.getByText("Phone setup needed", { exact: true })).toBeVisible();
  await expect(panel.getByText("Unknown", { exact: true })).toBeVisible();
  await expect(panel.getByText(/No qualified phone trackers/)).toBeVisible();
  await expect(panel.getByRole("button", { name: "Assign phone source" })).toHaveCount(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await panel.screenshot({ path: info.outputPath("presence-setup-needed.png") });
});

test("owner assignment sends opaque source not MAC or authority and renders governed result", async ({ page }) => {
  let assigned = false;
  await page.route("**/api/v1/presence?*", route => route.fulfill({ json: assigned ? { ...empty, items: [{ ...empty.items[0], binding_status: "CONFIGURED", value: "HOME", status: "CURRENT_KNOWN" }] } : empty }));
  await page.route("**/api/v1/presence/sources?*", route => route.fulfill({ json: { items: [{ source_handle: source, name: "Synthetic phone", signal_kind: "ROUTER_WIFI" }], next_cursor: null } }));
  const requests: unknown[] = [];
  await page.route("**/api/v1/presence/bind", route => {
    requests.push(route.request().postDataJSON()); assigned = true;
    return route.fulfill({ json: { status: "SUCCEEDED", operation: "household.presence.bind_source" } });
  });
  await page.getByRole("navigation").getByRole("button", { name: "Routines", exact: true }).click();
  const panel = page.getByRole("region", { name: "Household presence", exact: true });
  await panel.getByRole("combobox", { name: "Household member", exact: true }).selectOption(person);
  await panel.getByRole("combobox", { name: "Phone presence source", exact: true }).selectOption(source);
  await panel.getByRole("button", { name: "Assign phone source" }).click();
  await expect(panel.getByRole("status")).toContainText("Phone source assigned");
  await expect(panel.getByText("Home signal", { exact: true })).toBeVisible();
  expect(requests).toEqual([{ payload: { person_id: person, source_handle: source, freshness_seconds: 900 } }]);
  expect(JSON.stringify(requests)).not.toMatch(/mac|entity_id|household_id|role|assurance/);
});

test("provider unavailable replaces presence evidence with explicit error", async ({ page }) => {
  await page.route("**/api/v1/presence?*", route => route.fulfill({ status: 503, json: { detail: "HOUSEHOLD_PRESENCE_UNAVAILABLE" } }));
  await page.route("**/api/v1/presence/sources?*", route => route.fulfill({ status: 503, json: {} }));
  await page.getByRole("navigation").getByRole("button", { name: "Routines", exact: true }).click();
  const panel = page.getByRole("region", { name: "Household presence", exact: true });
  await expect(panel.getByRole("alert")).toContainText("no location is being assumed");
  await expect(panel.locator(".presence-cards article")).toHaveCount(0);
});
