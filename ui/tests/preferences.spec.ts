import { test, expect, type Page } from "@playwright/test";

// Requires the lead-owned serve_household_context.py fixture: dedicated synthetic
// PostgreSQL + real OPA/Graph/Memory. Never run these writes against owner runtime.
test.beforeEach(async ({ baseURL }) => {
  expect(baseURL).toBe("http://127.0.0.1:18293");
});
const editor = (page: Page) => page.locator(".preferences-panel");
async function open(page: Page) {
  await page.getByRole("navigation").getByRole("button", { name: "Preferences", exact: true }).click();
  await expect(editor(page).getByRole("heading", { name: "Saved preferences", exact: true })).toBeVisible();
}
async function saved(page: Page, query: string) {
  const response = await page.request.get(`/api/v1/preferences?limit=100&${query}`);
  expect(response.ok()).toBe(true);
  return response.json();
}

test("real Core saves shared and personal text, preserves provenance through correction, filters and retracts", async ({ page }, info) => {
  const errors: string[] = []; page.on("pageerror", error => errors.push(error.message));
  await page.goto("/auth/login");
  await expect(page.getByRole("heading", { name: /Welcome,/ })).toBeVisible();
  await open(page);
  const options = await saved(page, "");
  expect(options.can_edit).toBe(true); expect(options.members.length).toBeGreaterThan(0);
  const member = options.members[0];
  const marker = `Isolated preference regression ${info.project.name} ${Date.now()}`;
  const householdText = `${marker}: shared free-text context. Not an executable action.`;
  const personalText = `${marker}: personal free-text context. No permission is granted.`;
  await editor(page).getByRole("textbox", { name: "Preference", exact: true }).fill(householdText);
  await editor(page).getByRole("button", { name: "Save preference", exact: true }).click();
  await expect(editor(page).getByRole("status").filter({ hasText: "Preference saved" })).toBeVisible();
  const shared = (await saved(page, "scope=household")).items.find((item: { content: string }) => item.content === householdText);
  expect(shared).toBeDefined(); expect(shared.person_id).toBe(null);
  expect(shared.scope).toBe("household"); expect(shared.provenance.kind).toBe("EXPLICIT_INPUT");
  expect(shared.classification).toBe("OWNER_DECLARED_PREFERENCE"); expect(shared.authority).toBe("NONE");
  expect(shared.version).toBe(shared.preference_id);
  await editor(page).getByRole("combobox", { name: "Applies to", exact: true }).selectOption("personal");
  await editor(page).getByRole("combobox", { name: "Household member", exact: true }).selectOption(member.person_id);
  await editor(page).getByRole("combobox", { name: "Category", exact: true }).selectOption("notifications");
  await editor(page).getByRole("textbox", { name: "Preference", exact: true }).fill(personalText);
  await editor(page).getByRole("button", { name: "Save preference", exact: true }).click();
  await expect(editor(page).getByRole("status").filter({ hasText: "Preference saved" })).toBeVisible();
  const original = (await saved(page, `scope=personal&person_id=${member.person_id}&category=notifications`)).items.find((item: { content: string }) => item.content === personalText);
  expect(original).toBeDefined(); expect(original.person_id).toBe(member.person_id);
  expect(original.person_name).toBe(member.name); expect(original.authority).toBe("NONE");
  await page.reload(); await open(page);
  await editor(page).getByRole("combobox", { name: "Filter preferences", exact: true }).selectOption(member.person_id);
  const row = editor(page).locator(".preference-cards > li").filter({ hasText: marker });
  await expect(row).toHaveCount(1); await expect(row).toContainText(personalText);
  await row.getByRole("button", { name: "Edit preference" }).click();
  await expect(editor(page).getByRole("combobox", { name: "Household member", exact: true })).toHaveValue(member.person_id);
  const correction = `${marker}: corrected personal context, still not an action.`;
  await editor(page).getByRole("textbox", { name: "Preference", exact: true }).fill(correction);
  await editor(page).getByRole("button", { name: "Save correction" }).click();
  await expect(row).toContainText(correction);
  const corrected = (await saved(page, `person_id=${member.person_id}`)).items.find((item: { content: string }) => item.content === correction);
  expect(corrected.preference_id).not.toBe(original.preference_id);
  expect(corrected.supersedes_preference_id).toBe(original.preference_id);
  expect(corrected.provenance.kind).toBe("EXPLICIT_INPUT"); expect(corrected.authority).toBe("NONE");
  await row.getByText("Version & provenance").click();
  await expect(row).toContainText(corrected.version);
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: info.outputPath("real-core-personal-preference-test-data.png"), fullPage: true });
  await row.getByRole("button", { name: "Remove preference" }).click();
  await editor(page).getByRole("button", { name: "Keep preference" }).click(); await expect(row).toHaveCount(1);
  await row.getByRole("button", { name: "Remove preference" }).click();
  await editor(page).getByRole("button", { name: "Confirm removal" }).click();
  await expect(row).toHaveCount(0);
  await page.reload(); await open(page);
  expect((await saved(page, `person_id=${member.person_id}`)).items.some((item: { preference_id: string }) => item.preference_id === corrected.preference_id)).toBe(false);
  // Remove only this test's active shared preference via the same confirmed UI.
  await editor(page).getByRole("combobox", { name: "Filter preferences", exact: true }).selectOption("household");
  const sharedRow = editor(page).locator(".preference-cards > li").filter({ hasText: householdText });
  await sharedRow.getByRole("button", { name: "Remove preference" }).click();
  await editor(page).getByRole("button", { name: "Confirm removal" }).click();
  await expect(sharedRow).toHaveCount(0); expect(errors).toEqual([]);
});

test("real settings persist purple appearance and retain accessibility layout and widgets", async ({ page }, info) => {
  await page.emulateMedia({ colorScheme: "dark" });
  await page.goto("/auth/login"); await expect(page.getByRole("heading", { name: /Welcome,/ })).toBeVisible();
  const before = (await (await page.request.get("/api/v1/settings")).json()).settings;
  await page.getByRole("navigation").getByRole("button", { name: "Settings", exact: true }).click();
  await page.getByRole("combobox", { name: "Accent", exact: true }).selectOption("purple");
  await page.getByRole("combobox", { name: "Appearance", exact: true }).selectOption("night");
  await page.getByRole("button", { name: "Save preferences", exact: true }).click();
  await expect(page.locator("html")).toHaveAttribute("data-accent", "purple");
  await page.reload();
  const after = (await (await page.request.get("/api/v1/settings")).json()).settings;
  expect(after.accent).toBe("purple"); expect(after.appearance).toBe("night");
  for (const key of ["density", "text_scale", "reduced_motion", "display_mode", "visible_widgets", "widget_order"]) expect(after[key]).toEqual(before[key]);
  await expect.poll(() => page.evaluate(() => getComputedStyle(document.body).backgroundColor)).toBe("rgb(0, 0, 0)");
  expect(await page.evaluate(() => getComputedStyle(document.documentElement).getPropertyValue("--purple").trim())).toBe("#d84bff");
  await open(page);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: info.outputPath("real-core-purple-night-test-data.png"), fullPage: true });
});
